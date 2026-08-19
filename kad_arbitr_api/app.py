import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from kad_arbitr_api import ofdata_client as ofdata_module
from kad_arbitr_api.models import LegalCasesQuery, LegalCasesResult
from kad_arbitr_api.ofdata_client import OfdataClient, OfdataError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ofdata_module.ofdata_client = OfdataClient()
    try:
        yield
    finally:
        await ofdata_module.ofdata_client.aclose()


app = FastAPI(
    title="kad.arbitr.ru API",
    description=(
        "API для получения сведений об арбитражных делах компаний и ИП. "
        "Обёртка над официальным API ofdata.ru (данные Федеральных арбитражных судов)."
    ),
    version="0.2.0",
    lifespan=lifespan,
)


def get_client() -> OfdataClient:
    return ofdata_module.ofdata_client


@app.exception_handler(OfdataError)
async def _ofdata_error_handler(request: Request, exc: OfdataError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/legal-cases", response_model=LegalCasesResult)
async def legal_cases(
    query: LegalCasesQuery = Depends(),
    client: OfdataClient = Depends(get_client),
) -> LegalCasesResult:
    return await client.legal_cases(query)
