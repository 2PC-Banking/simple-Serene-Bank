"""
Interbank gateway API.

This lets the Serene demo UI initiate a transfer through the Java coordinator
without exposing coordinator topology in browser code.
"""

import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

router = APIRouter(prefix="/api/interbank", tags=["Interbank 2PC"])


class InterbankTransferRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_account: str = Field(..., alias="fromAccount")
    to_account: str = Field(..., alias="toAccount")
    amount: float
    note: str = ""
    destination_bank: str = Field("Family Banking", alias="destinationBank")
    client_tx_id: Optional[str] = Field(None, alias="clientTxId")
    scenario: str = "happy_path"


def _coordinator_url(path: str) -> str:
    return f"{settings.COORDINATOR_BASE_URL.rstrip('/')}{path}"


def _is_terminal(status: Optional[str]) -> bool:
    return status in {"COMMITTED", "ABORTED", "IN_DOUBT"}


def _normalize_response(payload: dict[str, Any], request: InterbankTransferRequest) -> dict[str, Any]:
    return {
        "success": payload.get("status") == "COMMITTED",
        "message": "Transfer committed by Java Coordinator"
        if payload.get("status") == "COMMITTED"
        else "Coordinator has not committed the transfer",
        "amount": request.amount,
        "transactionId": payload.get("transactionId") or payload.get("transaction_id"),
        "clientTxId": payload.get("clientTxId") or request.client_tx_id,
        "fromAccount": request.from_account,
        "toAccount": request.to_account,
        "destinationBank": request.destination_bank,
        "status": payload.get("status"),
        "phase": payload.get("phase"),
        "decision": payload.get("decision"),
        "participants": payload.get("participants", []),
        "scenario": request.scenario,
        "createdAt": payload.get("createdAt"),
        "updatedAt": payload.get("updatedAt"),
    }


def _get_status(client: httpx.Client, transaction_id: str) -> dict[str, Any]:
    response = client.get(_coordinator_url(f"/coordinator/transfers/{transaction_id}"))
    response.raise_for_status()
    return response.json()


def _scenario_participant_flags(scenario: str) -> tuple[dict[str, Any], dict[str, Any]]:
    source_flags: dict[str, Any] = {}
    dest_flags: dict[str, Any] = {}

    if scenario == "source_prepare_crash":
        source_flags["simulate_prepare_crash_before_vote"] = True
    elif scenario == "source_commit_fail_before_apply":
        source_flags["simulate_commit_fail_before_apply"] = True
    elif scenario == "source_commit_ack_lost":
        source_flags["simulate_commit_crash"] = True
    elif scenario == "source_rollback_ack_lost":
        source_flags["simulate_rollback_crash_after_apply"] = True
    elif scenario == "dest_prepare_crash":
        dest_flags["simulate_prepare_crash_before_vote"] = True
    elif scenario == "dest_commit_ack_lost":
        dest_flags["simulate_commit_crash"] = True

    return source_flags, dest_flags


def _health_probe(client: httpx.Client, name: str, url: str) -> dict[str, Any]:
    try:
        response = client.get(url)
        response.raise_for_status()
        return {
            "name": name,
            "online": True,
            "status": response.status_code,
            "url": url,
        }
    except httpx.HTTPError as exc:
        return {
            "name": name,
            "online": False,
            "error": str(exc),
            "url": url,
        }


@router.get("/services")
def service_status():
    family_health_url = f"{settings.FAMILY_PARTICIPANT_PUBLIC_URL.rstrip('/')}/api/recovery/status"
    with httpx.Client(timeout=4.0) as client:
        return {
            "services": [
                {
                    "name": "Serene Gateway",
                    "online": True,
                    "url": "local FastAPI",
                },
                _health_probe(client, "Java Coordinator", _coordinator_url("/coordinator/health")),
                _health_probe(client, "Family Backend", family_health_url),
            ]
        }


@router.post("/transfer-2pc")
def transfer_2pc(request: InterbankTransferRequest):
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")

    client_tx_id = request.client_tx_id or f"WEB-SERENE-{int(time.time() * 1000)}"
    source_flags, dest_flags = _scenario_participant_flags(request.scenario)
    coordinator_payload = {
        "client_tx_id": client_tx_id,
        "from_account": request.from_account,
        "to_account": request.to_account,
        "amount": request.amount,
        "currency": "VND",
        "participants": [
            {
                "name": "simple-serene-bank-source",
                "base_url": settings.SIMPLE_PARTICIPANT_PUBLIC_URL,
                "account_id": request.from_account,
                "operation": "DEBIT",
                **source_flags,
            },
            {
                "name": "family-bank-dest",
                "base_url": settings.FAMILY_PARTICIPANT_PUBLIC_URL,
                "account_id": request.to_account,
                "operation": "CREDIT",
                **dest_flags,
            },
        ],
        "timeout_ms": 3000,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(_coordinator_url("/coordinator/transfers"), json=coordinator_payload)
            response.raise_for_status()
            current = response.json()
            transaction_id = current.get("transactionId") or current.get("transaction_id")
            if not transaction_id:
                raise HTTPException(status_code=502, detail="Coordinator response did not include transactionId")

            for _ in range(5):
                if _is_terminal(current.get("status")):
                    break
                time.sleep(0.7)
                current = _get_status(client, transaction_id)

            request.client_tx_id = client_tx_id
            return _normalize_response(current, request)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Coordinator request failed: {exc}") from exc


@router.get("/transfer-2pc/{transaction_id}")
def get_transfer_status(transaction_id: str):
    try:
        with httpx.Client(timeout=10.0) as client:
            return _get_status(client, transaction_id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Coordinator request failed: {exc}") from exc


@router.post("/transfer-2pc/{transaction_id}/retry-decision")
def retry_transfer_decision(transaction_id: str):
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(_coordinator_url(f"/coordinator/transfers/{transaction_id}/retry-decision"), json={})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Coordinator retry failed: {exc}") from exc
