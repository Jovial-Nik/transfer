"""Ties kad_client, pochta_client, the registry and the notifier together into
one daily cycle. One court source failing must not stop the parcel leg, and
vice versa — see run_once()."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from legal_monitor.core import registry
from legal_monitor.doc_analyzer.apk_rules import compute_rule_deadline
from legal_monitor.doc_analyzer.client import DocumentAnalysisFailed, DocumentAnalyzer
from legal_monitor.kad_client.exceptions import KadUnavailable
from legal_monitor.kad_client.search import KadClient
from legal_monitor.notifier.formatter import CaseEventDisplay, CaseUpdate, EventAnalysisDisplay, ParcelUpdate, RunSummary, build_messages
from legal_monitor.notifier.telegram import TelegramNotifier
from legal_monitor.pochta_client.client import PochtaClient, PochtaUnavailable

logger = logging.getLogger(__name__)


@dataclass
class KadCardFetcher:
    """Thin seam so the orchestrator doesn't import Playwright directly and
    tests can substitute a fake. `fetch` must return a card.CaseCardData."""

    kad_client: KadClient
    user_agent: str
    executable_path: str | None = None

    def fetch(self, case_guid: str):
        import asyncio

        from legal_monitor.kad_client.card import fetch_card

        cookies = self.kad_client._cookie_service.get_cookies(force=False)
        return asyncio.run(fetch_card(case_guid, cookies, self.user_agent, self.executable_path))


@dataclass
class DocumentAnalysisRunner:
    """Thin seam bundling document download (needs KAD cookies) + Claude analysis.
    Pass analyzer=None to disable this feature entirely (e.g. no ANTHROPIC_API_KEY
    configured) — analyze() then returns None instead of raising, and the
    orchestrator skips it silently rather than treating it as a failure."""

    kad_client: KadClient
    user_agent: str
    analyzer: DocumentAnalyzer | None

    def analyze(self, document_url: str):
        if self.analyzer is None:
            return None

        from legal_monitor.kad_client.documents import download_document

        cookies = self.kad_client._cookie_service.get_cookies(force=False)
        pdf_bytes = download_document(document_url, cookies, self.user_agent)
        return self.analyzer.analyze(pdf_bytes)


def run_once(
    conn: sqlite3.Connection,
    kad_client: KadClient,
    card_fetcher: KadCardFetcher,
    pochta_client: PochtaClient,
    telegram: TelegramNotifier,
    default_claim_response_days: int,
    doc_analysis_runner: DocumentAnalysisRunner | None = None,
    dry_run: bool = False,
) -> RunSummary:
    run_id = registry.start_run(conn)
    kad_ok, kad_error, case_updates = _run_kad_leg(conn, kad_client, card_fetcher, doc_analysis_runner)
    pochta_ok, pochta_error, parcel_updates = _run_pochta_leg(conn, pochta_client, default_claim_response_days)

    new_items = sum(len(u.new_events) + len(u.new_hearings) for u in case_updates) + len(parcel_updates)
    registry.finish_run(
        conn,
        run_id,
        kad_ok=kad_ok,
        pochta_ok=pochta_ok,
        new_items=new_items,
        error=" | ".join(e for e in (kad_error, pochta_error) if e) or None,
    )

    summary = RunSummary(
        run_date=date.today(),
        kad_ok=kad_ok,
        kad_error=kad_error,
        pochta_ok=pochta_ok,
        pochta_error=pochta_error,
        case_updates=case_updates,
        parcel_updates=parcel_updates,
    )

    messages = build_messages(summary)
    if dry_run:
        for m in messages:
            print(m)
            print("---")
        if not messages:
            print("(нечего отправлять — тишина по умолчанию)")
    elif messages:
        telegram.send(messages)

    return summary


def _run_kad_leg(
    conn: sqlite3.Connection,
    kad_client: KadClient,
    card_fetcher: KadCardFetcher,
    doc_analysis_runner: DocumentAnalysisRunner | None = None,
):
    cases = registry.list_cases(conn, active_only=True)
    if not cases:
        return True, None, []

    case_updates: list[CaseUpdate] = []
    try:
        headers = kad_client.search([c["case_number"] for c in cases])
    except KadUnavailable as exc:
        logger.error("KAD leg failed: %s", exc)
        return False, str(exc), []

    headers_by_number = {h.case_number: h for h in headers}

    for case in cases:
        header = headers_by_number.get(case["case_number"])
        if header is None:
            logger.warning("case %s not found in this search — leaving untouched", case["case_number"])
            continue

        guid = header.case_guid or case["case_guid"]
        if guid is None:
            logger.warning("no case_guid for %s yet, cannot fetch its card", case["case_number"])
            continue

        try:
            card = card_fetcher.fetch(guid)
        except Exception:
            logger.exception("failed to fetch card for %s (%s)", case["case_number"], guid)
            continue

        registry.update_case_meta(conn, case["case_number"], guid, header.court, header.judge, not card.is_finished)

        update = CaseUpdate(case_number=case["case_number"], counterparty=case["counterparty"])
        for event in card.events:
            new_event_id = registry.record_case_event(conn, case["id"], case["case_number"], event)
            if new_event_id is None:
                continue
            analysis_display = None
            if event.document_url and doc_analysis_runner is not None:
                analysis_display = _analyze_and_record(conn, new_event_id, event, doc_analysis_runner)
            update.new_events.append(CaseEventDisplay(event=event, analysis=analysis_display))
        for hearing in card.hearings:
            if registry.record_hearing(conn, case["id"], case["case_number"], hearing):
                update.new_hearings.append(hearing)

        if update.new_events or update.new_hearings:
            case_updates.append(update)

    return True, None, case_updates


def _analyze_and_record(conn: sqlite3.Connection, case_event_id: int, event, doc_analysis_runner: DocumentAnalysisRunner) -> EventAnalysisDisplay:
    import json

    try:
        analysis = doc_analysis_runner.analyze(event.document_url)
    except Exception as exc:  # noqa: BLE001 - a bad PDF/API call must not stop the run
        logger.exception("document analysis failed for event %s", case_event_id)
        registry.record_document_analysis(
            conn, case_event_id, document_type="", summary="", explicit_deadlines_json="[]",
            rule_deadline=None, rule_deadline_basis=None, analysis_error=str(exc),
        )
        return EventAnalysisDisplay(error=str(exc))

    rule_result = compute_rule_deadline(analysis.document_type, event.event_date)
    rule_deadline, rule_basis = rule_result if rule_result else (None, None)

    explicit = analysis.explicit_deadlines
    explicit_deadline = explicit[0].deadline_date if explicit and explicit[0].deadline_date else None
    explicit_basis = f"явно указано в документе: {explicit[0].description}" if explicit else None

    # Prefer a date explicitly stated in the text over the statutory default — the
    # document itself is more reliable than a generic rule when both are present.
    deadline, basis = (explicit_deadline, explicit_basis) if explicit_deadline else (rule_deadline, rule_basis)

    registry.record_document_analysis(
        conn,
        case_event_id,
        document_type=analysis.document_type.value,
        summary=analysis.summary,
        explicit_deadlines_json=json.dumps([d.model_dump(mode="json") for d in explicit], ensure_ascii=False),
        rule_deadline=rule_deadline,
        rule_deadline_basis=rule_basis,
    )
    return EventAnalysisDisplay(summary=analysis.summary, deadline=deadline, deadline_basis=basis)


def _run_pochta_leg(conn: sqlite3.Connection, pochta_client: PochtaClient, default_response_days: int):
    parcels = registry.list_parcels(conn, active_only=True)
    if not parcels:
        return True, None, []

    parcel_updates: list[ParcelUpdate] = []
    errors: list[str] = []
    for parcel in parcels:
        try:
            snapshot = pochta_client.get_operation_history(parcel["barcode"])
        except PochtaUnavailable as exc:
            logger.error("Pochta leg failed for %s: %s", parcel["barcode"], exc)
            errors.append(f"{parcel['barcode']}: {exc}")
            continue

        registry.update_parcel_status(conn, parcel["barcode"], snapshot.status, snapshot.delivered_at, not snapshot.is_final)

        response_days = parcel["claim_response_days"] or default_response_days
        deadline = snapshot.delivered_at + timedelta(days=response_days) if snapshot.delivered_at else None

        any_new = False
        for event in snapshot.events:
            if registry.record_parcel_event(conn, parcel["id"], parcel["barcode"], event):
                any_new = True

        if any_new:
            parcel_updates.append(
                ParcelUpdate(
                    claim_ref=parcel["claim_ref"] or parcel["barcode"],
                    counterparty=parcel["counterparty"] or "",
                    status=snapshot.status,
                    delivered_at=snapshot.delivered_at,
                    response_deadline=deadline,
                )
            )

    error = "; ".join(errors) if errors else None
    return not errors, error, parcel_updates
