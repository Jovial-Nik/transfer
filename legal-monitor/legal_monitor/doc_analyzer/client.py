"""Sends a case document (PDF) to Claude for classification, summarization,
and deadline extraction.

NOT LIVE-VERIFIED: no real KAD document was available to test against (see
docs/kad-endpoints.md — the card-page reconnaissance that would produce a
document_url was never completed). The request shape below follows the
documented PDF-input + structured-output pattern exactly (base64 `document`
content block, `output_config.format` json_schema, no beta header needed)
and should work once a real PDF reaches it — but it has not been exercised
end to end.

Model: claude-opus-5 by default. This is a deliberately un-downgraded choice
— legal deadline extraction is exactly the kind of task where a
classification error has real consequences, and the brief itself says
computed deadlines are always to be checked manually regardless. Override
via ANTHROPIC_MODEL if you want to trade accuracy for cost on a lower tier.
"""

from __future__ import annotations

import base64
import json
import logging

from anthropic import Anthropic

from legal_monitor.doc_analyzer.schemas import DocumentAnalysis

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5"
MAX_TOKENS = 8000

SYSTEM_PROMPT = (
    "Ты помогаешь юристу отслеживать арбитражные дела о взыскании задолженности "
    "по договорам поставки. Тебе дают PDF судебного документа (решение, определение). "
    "Классифицируй документ, кратко изложи его суть простым языком для занятого юриста "
    "и выпиши дословно все сроки, прямо указанные в тексте (что сделать и к какой дате). "
    "Не придумывай сроки, которых нет в тексте — для них есть отдельный расчёт по кодексу "
    "в другом месте системы. Если документ не подходит ни под одну конкретную категорию, "
    "используй тип \"иное\"."
)


class DocumentAnalysisFailed(Exception):
    pass


class DocumentAnalyzer:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def analyze(self, pdf_bytes: bytes, filename: str = "document.pdf") -> DocumentAnalysis:
        encoded = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        schema = DocumentAnalysis.model_json_schema()

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "high",
                    "format": {"type": "json_schema", "schema": schema},
                },
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {"type": "base64", "media_type": "application/pdf", "data": encoded},
                                "title": filename,
                            },
                            {"type": "text", "text": "Проанализируй этот документ по инструкции в system prompt."},
                        ],
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001 - any API/network failure degrades this one document, not the run
            raise DocumentAnalysisFailed(f"Claude API: {exc}") from exc

        if response.stop_reason == "refusal":
            raise DocumentAnalysisFailed("Claude отказался анализировать документ (stop_reason=refusal)")

        text_blocks = [b.text for b in response.content if b.type == "text"]
        if not text_blocks:
            raise DocumentAnalysisFailed(f"пустой ответ от Claude, stop_reason={response.stop_reason}")

        try:
            data = json.loads(text_blocks[0])
            return DocumentAnalysis.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise DocumentAnalysisFailed(f"не удалось разобрать структурированный ответ: {exc}") from exc
