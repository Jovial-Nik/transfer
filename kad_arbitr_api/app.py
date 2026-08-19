import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from kad_arbitr_api.browser import CaptchaDetected, NoVerifiedSession, kad_browser
from kad_arbitr_api.client import KadArbitrClient
from kad_arbitr_api.models import CaseDetails, CaseDocument, SearchParams, SearchResult

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await kad_browser.start()
    try:
        yield
    finally:
        await kad_browser.stop()


app = FastAPI(
    title="kad.arbitr.ru API",
    description="API для извлечения информации о делах и документов из картотеки арбитражных дел",
    version="0.1.0",
    lifespan=lifespan,
)

client = KadArbitrClient(kad_browser)


@app.exception_handler(CaptchaDetected)
@app.exception_handler(NoVerifiedSession)
async def _unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/search", response_model=SearchResult)
async def search(params: SearchParams) -> SearchResult:
    return await client.search(params)


@app.get("/cases/{case_id}", response_model=CaseDetails)
async def get_case(case_id: str) -> CaseDetails:
    return await client.get_case(case_id)


@app.get("/cases/{case_id}/documents", response_model=list[CaseDocument])
async def list_documents(case_id: str) -> list[CaseDocument]:
    return await client.list_documents(case_id)


@app.get("/documents/{case_id}/{document_index}")
async def download_document(case_id: str, document_index: int) -> Response:
    documents = await client.list_documents(case_id)
    document = next(
        (d for d in documents if d.document_id == f"{case_id}:{document_index}"), None
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Документ не найден")

    body, content_type = await client.download_document(document.file_url)
    return Response(content=body, media_type=content_type)
