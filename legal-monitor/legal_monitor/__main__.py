"""CLI: python -m legal_monitor <command>.

    add-case <number> --counterparty ... --role plaintiff|defendant|third_party
    add-parcel <barcode> --claim ... --counterparty ... [--response-days N]
    list [--active-only]
    run --once [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys

from legal_monitor.config import get_settings
from legal_monitor.cookie_service.service import CookieService
from legal_monitor.core import db, orchestrator, registry
from legal_monitor.kad_client.search import KadClient
from legal_monitor.notifier.telegram import TelegramNotifier
from legal_monitor.pochta_client.client import PochtaClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legal_monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    add_case = sub.add_parser("add-case")
    add_case.add_argument("case_number")
    add_case.add_argument("--counterparty", required=True)
    add_case.add_argument("--role", required=True, choices=["plaintiff", "defendant", "third_party"])

    add_parcel = sub.add_parser("add-parcel")
    add_parcel.add_argument("barcode")
    add_parcel.add_argument("--claim", required=True, dest="claim_ref")
    add_parcel.add_argument("--counterparty", required=True)
    add_parcel.add_argument("--response-days", type=int, default=None)

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--active", action="store_true", help="only show active cases/parcels")

    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("--once", action="store_true", required=True)
    run_cmd.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args = _build_parser().parse_args(argv)
    conn = db.connect(settings.db_path)
    db.init_db(conn)

    if args.command == "add-case":
        added = registry.add_case(conn, args.case_number, args.counterparty, args.role)
        print("добавлено" if added else "уже отслеживается")
        return 0

    if args.command == "add-parcel":
        added = registry.add_parcel(conn, args.barcode, args.claim_ref, args.counterparty, args.response_days)
        print("добавлено" if added else "уже отслеживается")
        return 0

    if args.command == "list":
        print("Дела:")
        for c in registry.list_cases(conn, active_only=args.active):
            print(f"  {c['case_number']}  {c['counterparty']}  ({c['our_role']})  active={bool(c['is_active'])}")
        print("Отправления:")
        for p in registry.list_parcels(conn, active_only=args.active):
            print(f"  {p['barcode']}  {p['claim_ref']}  {p['status']}  active={bool(p['is_active'])}")
        return 0

    if args.command == "run":
        cookie_service = CookieService(cache_path=settings.cookies_cache_path, user_agent=settings.kad_user_agent)
        kad_client = KadClient(cookie_service=cookie_service, user_agent=settings.kad_user_agent)
        card_fetcher = orchestrator.KadCardFetcher(kad_client=kad_client, user_agent=settings.kad_user_agent)
        pochta_client = PochtaClient(login=settings.pochta_login, password=settings.pochta_password)
        telegram = TelegramNotifier(bot_token=settings.telegram_bot_token, chat_id=settings.telegram_chat_id)

        orchestrator.run_once(
            conn,
            kad_client,
            card_fetcher,
            pochta_client,
            telegram,
            default_claim_response_days=settings.default_claim_response_days,
            dry_run=args.dry_run,
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
