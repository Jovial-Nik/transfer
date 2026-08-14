"""Structured shape Claude must fill in when reading a case document.

`document_type` is a closed enum, not free text, on purpose: `apk_rules.py`
keys its statutory-deadline table off this value, so the classification has
to be something code can switch on. Keep this enum small and each member
legally unambiguous — "иное" is the safe default for anything that doesn't
clearly fit, and carries no automatic deadline.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(str, Enum):
    RESHENIE_OBSHEE = "решение_обычное_производство"
    RESHENIE_UPROSHENNOE = "решение_упрощенное_производство"
    OPREDELENIE_BEZ_DVIZHENIYA = "определение_оставление_без_движения"
    OPREDELENIE_OBSHEE = "определение_общее"
    INOE = "иное"


class ExtractedDeadline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(description="Что нужно сделать и к какому сроку, простыми словами")
    deadline_date: date | None = Field(default=None, description="Конкретная календарная дата, если она прямо указана в тексте")
    deadline_days: int | None = Field(default=None, description="Срок в днях/месяцах от даты документа, если дата не указана явно (месяц считать за 30 дней)")
    quote: str = Field(description="Дословная цитата из документа, на основании которой извлечён срок")


class DocumentAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    summary: str = Field(description="2-4 предложения простым языком: что это за документ и что он означает для нашей стороны")
    key_facts: list[str] = Field(default_factory=list, description="Короткие пункты с ключевыми фактами документа")
    explicit_deadlines: list[ExtractedDeadline] = Field(
        default_factory=list, description="Все сроки, прямо указанные в тексте документа"
    )
