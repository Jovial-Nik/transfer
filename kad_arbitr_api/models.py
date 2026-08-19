from typing import Optional

from pydantic import BaseModel, Field


class SearchParams(BaseModel):
    participant: Optional[str] = Field(default=None, description="Наименование участника дела")
    judge: Optional[str] = Field(default=None, description="ФИО судьи")
    court: Optional[str] = Field(default=None, description="Наименование суда")
    case_number: Optional[str] = Field(default=None, description="Номер дела")
    date_from: Optional[str] = Field(default=None, description="Дата регистрации, начало периода, дд.мм.гггг")
    date_to: Optional[str] = Field(default=None, description="Дата регистрации, конец периода, дд.мм.гггг")
    page: int = Field(default=1, ge=1, description="Номер страницы результатов")


class CaseSummary(BaseModel):
    case_id: str = Field(description="Идентификатор дела (GUID из ссылки /Card/{id})")
    case_number: str
    court: Optional[str] = None
    judge: Optional[str] = None
    plaintiffs: list[str] = Field(default_factory=list)
    defendants: list[str] = Field(default_factory=list)
    registration_date: Optional[str] = None
    url: str


class CaseDocument(BaseModel):
    document_id: str = Field(description="Идентификатор документа для скачивания через /documents/{document_id}")
    title: str
    document_date: Optional[str] = None
    instance: Optional[str] = None
    file_url: str = Field(description="Прямая ссылка на файл на kad.arbitr.ru")


class CaseParty(BaseModel):
    role: str = Field(description='Например "Истец" или "Ответчик"')
    name: str


class CaseDetails(BaseModel):
    case_id: str
    case_number: str
    court: Optional[str] = None
    judge: Optional[str] = None
    case_type: Optional[str] = None
    parties: list[CaseParty] = Field(default_factory=list)
    documents: list[CaseDocument] = Field(default_factory=list)
    url: str


class SearchResult(BaseModel):
    page: int
    items: list[CaseSummary]
    has_next_page: bool
