"""Statutory deadlines from the АПК РФ for the small set of document types in
DocumentType that have an unambiguous, generally-applicable rule.

Deliberately not exhaustive. "определение_общее" uses ст. 188 АПК РФ's own
default rule (1 month, "если иное не установлено настоящим Кодексом") — that
carve-out is the reason this is safe to automate for that bucket: it's the
Code's own fallback, not this project's guess. Anything more specific than
that (обеспечительные меры, отдельные виды определений с иным сроком, etc.)
is exactly the kind of case that carve-out exists for, which is why it isn't
in this table — the classifier should put those under "иное" rather than
force-fit them here, and a human checks "иное" cases manually.

Every result carries the statute citation so whoever reads the Telegram
message can verify it in one glance — this is not a substitute for that
check, per the disclaimer in README.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from legal_monitor.doc_analyzer.schemas import DocumentType


@dataclass(frozen=True)
class Rule:
    days: int
    statute: str


RULES: dict[DocumentType, Rule] = {
    DocumentType.RESHENIE_OBSHEE: Rule(days=30, statute="ст. 259 АПК РФ — 1 месяц со дня принятия решения в полном объёме"),
    DocumentType.RESHENIE_UPROSHENNOE: Rule(days=15, statute="ст. 229 АПК РФ — 15 дней (упрощённое производство)"),
    DocumentType.OPREDELENIE_OBSHEE: Rule(days=30, statute="ст. 188 АПК РФ — 1 месяц (общее правило для определений)"),
}


def compute_rule_deadline(document_type: DocumentType, trigger_date: date | None) -> tuple[date, str] | None:
    """Returns (deadline_date, human-readable basis) or None when no rule applies
    (either the type has no fixed rule, or there's no trigger date to count from)."""
    if trigger_date is None:
        return None
    rule = RULES.get(document_type)
    if rule is None:
        return None
    return trigger_date + timedelta(days=rule.days), rule.statute
