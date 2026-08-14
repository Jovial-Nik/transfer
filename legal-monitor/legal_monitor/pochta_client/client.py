"""SOAP client for the Pochta Rossii single-access tracking API.

VERIFIED against the live WSDL (https://tracking.pochta.ru/rtm34?wsdl,
fetched 2026-08-14): the operation is `getOperationHistory` on port
`OperationHistory12`, taking `OperationHistoryRequest{Barcode, MessageType,
Language}` and `AuthorizationHeader{login, password}` as two ordinary body
elements (not a WS-Security SOAP header, despite the name) and returning
`OperationHistoryData{historyRecord[]}`, each record carrying
OperationParameters.OperType/OperAttr (human-readable Russian names) and
OperDate, plus AddressParameters.OperationAddress.Description for location.
This matches the brief's method name exactly.

LIVE-VERIFIED (2026-08-14, placeholder login/password "x"/"x"): a real call to
this client against the real tracking.pochta.ru/rtm34 endpoint returns a SOAP
fault with message "Ошибка авторизации" — i.e. the server parsed the request,
validated the schema, and rejected it specifically for bad credentials. That
confirms the WSDL, operation name, and OperationHistoryRequest/
AuthorizationHeader shape used below are all correct end to end; only real
POCHTA_LOGIN/POCHTA_PASSWORD are needed to get real data. What is NOT
verified: the status classification below (which OperType/OperAttr text
counts as "significant" vs. routine transit noise), since that needs a real
successful response with a real barcode to check against.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

import zeep
from zeep.exceptions import Fault

from legal_monitor.core.models import ParcelEventData, ParcelSnapshot

logger = logging.getLogger(__name__)

WSDL_URL = "https://tracking.pochta.ru/rtm34?wsdl"

# Substrings matched against "<OperType.Name> <OperAttr.Name>", lowercased.
# Routine sorting-center transit isn't in this list on purpose — it's noise.
DELIVERED_MARKERS = ("вручен",)
FAILED_ATTEMPT_MARKERS = ("неудачная попытка вручения",)
RETURN_MARKERS = ("возврат",)
ARRIVED_AT_DELIVERY_POINT_MARKERS = ("прибытие в место вручения",)

SIGNIFICANT_MARKERS = (
    DELIVERED_MARKERS + FAILED_ATTEMPT_MARKERS + RETURN_MARKERS + ARRIVED_AT_DELIVERY_POINT_MARKERS
)


class PochtaUnavailable(Exception):
    pass


@dataclass
class _RawRecord:
    oper_type: str
    oper_attr: str
    oper_date: datetime | None
    location: str

    @property
    def label(self) -> str:
        return f"{self.oper_type} {self.oper_attr}".strip()

    @property
    def is_significant(self) -> bool:
        lowered = self.label.lower()
        return any(marker in lowered for marker in SIGNIFICANT_MARKERS)

    @property
    def is_delivered(self) -> bool:
        return "вручен" in self.label.lower() and "неудачная попытка" not in self.label.lower()

    @property
    def is_returned(self) -> bool:
        return "возврат" in self.label.lower()


class PochtaClient:
    def __init__(self, login: str, password: str) -> None:
        self._login = login
        self._password = password
        self._zeep_client: zeep.Client | None = None
        self.request_count = 0

    def _client(self) -> zeep.Client:
        if self._zeep_client is None:
            self._zeep_client = zeep.Client(wsdl=WSDL_URL)
        return self._zeep_client

    def get_operation_history(self, barcode: str) -> ParcelSnapshot:
        """One barcode = one request, per the brief's rate-limit accounting."""
        client = self._client()
        auth = {"login": self._login, "password": self._password}
        request = {"Barcode": barcode, "MessageType": 0, "Language": "RUS"}

        self.request_count += 1
        logger.info("Pochta: getOperationHistory(%s) — request #%d today", barcode, self.request_count)

        try:
            response = client.service.getOperationHistory(OperationHistoryRequest=request, AuthorizationHeader=auth)
        except Fault as exc:
            raise PochtaUnavailable(f"Почта России SOAP fault для {barcode}: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - network/WSDL errors surface as generic exceptions in zeep
            raise PochtaUnavailable(f"Почта России недоступна для {barcode}: {exc}") from exc

        records = [_to_raw_record(r) for r in (response.historyRecord or [])]
        records.sort(key=lambda r: r.oper_date or datetime.min)
        return _to_snapshot(barcode, records)


def _to_raw_record(record) -> _RawRecord:
    op = record.OperationParameters
    addr = record.AddressParameters
    return _RawRecord(
        oper_type=getattr(op.OperType, "Name", "") or "",
        oper_attr=getattr(op.OperAttr, "Name", "") or "",
        oper_date=op.OperDate,
        location=getattr(addr.OperationAddress, "Description", "") or "",
    )


def _to_snapshot(barcode: str, records: list[_RawRecord]) -> ParcelSnapshot:
    events = [
        ParcelEventData(operation=r.label, operation_at=r.oper_date, location=r.location)
        for r in records
        if r.is_significant
    ]

    latest = records[-1] if records else None
    status = latest.label if latest else "нет данных"
    delivered_at: date | None = None
    is_final = False

    for r in records:
        if r.is_delivered:
            delivered_at = r.oper_date.date() if r.oper_date else None
            is_final = True
        elif r.is_returned and delivered_at is None:
            is_final = False  # "возврат" alone is transit; final only once actually handed back (is_delivered)

    return ParcelSnapshot(barcode=barcode, status=status, delivered_at=delivered_at, is_final=is_final, events=events)
