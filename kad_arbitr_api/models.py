from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class LegalCasesQuery(BaseModel):
    """Параметры запроса к /legal-cases. Нужно указать inn или ogrn."""

    inn: Optional[str] = Field(default=None, description="ИНН компании или ИП")
    ogrn: Optional[str] = Field(default=None, description="ОГРН компании или ОГРНИП")
    kpp: Optional[str] = Field(default=None, description="КПП (уточняет вместе с ИНН)")
    role: Optional[Literal["plaintiff", "defendant"]] = Field(
        default=None, description="Роль в деле: истец или ответчик"
    )
    active: Optional[bool] = Field(default=None, description="Только незавершённые дела")
    date_from: Optional[str] = Field(default=None, description="Дата начала периода, ГГГГ-ММ-ДД")
    date_to: Optional[str] = Field(default=None, description="Дата конца периода, ГГГГ-ММ-ДД")
    claim_amount_from: Optional[float] = Field(default=None, description="Мин. сумма иска")
    claim_amount_to: Optional[float] = Field(default=None, description="Макс. сумма иска")
    page: int = Field(default=1, ge=1, description="Номер страницы")
    sort: Optional[Literal["date", "-date"]] = Field(default=None, description="Сортировка по дате")

    @model_validator(mode="after")
    def _require_inn_or_ogrn(self) -> "LegalCasesQuery":
        if not self.inn and not self.ogrn:
            raise ValueError("Нужно указать inn или ogrn")
        return self


class CaseParty(BaseModel):
    inn: Optional[str] = Field(default=None, alias="ИНН")
    name: Optional[str] = Field(default=None, alias="Наим")
    address: Optional[str] = Field(default=None, alias="Адрес")

    model_config = {"populate_by_name": True}


class LegalCase(BaseModel):
    case_number: str = Field(alias="Номер")
    case_id: str = Field(alias="UUID")
    kad_url: Optional[str] = Field(default=None, alias="СтрКАД")
    date: Optional[str] = Field(default=None, alias="Дата")
    court: Optional[str] = Field(default=None, alias="Суд")
    plaintiffs: list[CaseParty] = Field(default_factory=list, alias="Ист")
    defendants: list[CaseParty] = Field(default_factory=list, alias="Ответ")
    claim_amount: Optional[float] = Field(default=None, alias="СуммИск")

    model_config = {"populate_by_name": True}


class LegalCasesResult(BaseModel):
    total_records: int = Field(alias="ЗапВсего")
    total_pages: int = Field(alias="СтрВсего")
    current_page: int = Field(alias="СтрТекущ")
    total_claim_amount: Optional[float] = Field(default=None, alias="ОбщСуммИск")
    cases: list[LegalCase] = Field(default_factory=list, alias="Записи")

    model_config = {"populate_by_name": True}
