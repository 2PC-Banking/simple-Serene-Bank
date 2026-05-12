"""Prepare API - Endpoint cho PREPARE phase của 2PC."""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.prepare_schema import (
    CoordinatorPreparePayloadResponse,
    PrepareRequest,
    PrepareResponse,
)
from app.services.transaction_service import TransactionService
from app.utils.logger import log_error, log_transaction
from app.api.simulation import get_current_receiver_simulation

router = APIRouter(prefix="/api", tags=["2PC - Prepare"])


@router.post("/prepare", response_model=PrepareResponse)
def prepare(request: PrepareRequest, db: Session = Depends(get_db)):
    """
    PREPARE Phase (Phase 1) của Two-Phase Commit.
    
    Coordinator gửi request prepare, Participant kiểm tra điều kiện:
    - Tài khoản tồn tại
    - Tài khoản chưa bị khóa
    - Số dư đủ (nếu DEBIT)
    
    Nếu OK → lock account, ghi log PREPARED, trả vote=YES
    Nếu FAIL → trả lỗi tương ứng
    """
    try:
        if request.operation.value == "CREDIT":
            sim = get_current_receiver_simulation()
            request.simulate_delay_ms = max(request.simulate_delay_ms, sim.simulate_delay_ms)
            if sim.simulate_prepare_crash_before_vote:
                request.simulate_crash_before_vote = True

        if request.simulate_delay_ms > 0:
            log_transaction(
                request.transaction_id,
                "PREPARE",
                f"Simulating delay {request.simulate_delay_ms}ms before vote",
            )
            time.sleep(request.simulate_delay_ms / 1000)

        from app.models.account_model import Account
        from app.models.transaction_model import TransactionLog
        from decimal import Decimal

        # Ghi log INIT ngay từ đầu để UI có thể hiển thị
        account = db.query(Account).filter(Account.account_id == request.account_id).first()
        
        # Luôn ghi log INIT ngay từ đầu để UI có thể hiển thị kể cả khi sai tài khoản
        existing = db.query(TransactionLog).filter(
            TransactionLog.transaction_id == request.transaction_id,
            TransactionLog.account_id == request.account_id
        ).first()
        if not existing:
            tx_init = TransactionLog(
                transaction_id=request.transaction_id,
                account_id=request.account_id,
                operation=request.operation.value,
                amount=Decimal(str(request.amount)),
                status="INIT"
            )
            db.add(tx_init)
            db.commit()

        if request.simulate_crash_before_vote:
            log_error(request.transaction_id, "PREPARE", "Simulated crash before vote response")
            raise HTTPException(
                status_code=500,
                detail=(
                    "Crash simulated in Phase 1: participant stopped before returning vote to coordinator"
                ),
            )

        result = TransactionService.prepare(
            db=db,
            transaction_id=request.transaction_id,
            account_id=request.account_id,
            operation=request.operation.value,
            amount=request.amount,
        )
        return PrepareResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        log_error(request.transaction_id, "PREPARE", str(e))
        db.rollback()
        
        # Nếu lỗi nghiệp vụ (như không đủ tiền, sai tài khoản), ghi log ABORTED để UI thấy
        existing = db.query(TransactionLog).filter(
            TransactionLog.transaction_id == request.transaction_id,
            TransactionLog.account_id == request.account_id
        ).first()
        if existing and existing.status == "INIT":
            existing.status = "ABORTED"
            db.commit()
                
        # Thay vì văng lỗi 500, trả về vote NO cho Coordinator
        return PrepareResponse(
            transaction_id=request.transaction_id,
            vote="NO",
            message=str(e),
            account_id=request.account_id,
            operation=request.operation.value,
            amount=request.amount
        )


@router.post("/prepare/coordinator-payload", response_model=CoordinatorPreparePayloadResponse)
def prepare_coordinator_payload(request: PrepareRequest):
    """Chuẩn hóa payload để frontend/coordinator gửi sang participant ở Phase 1."""
    notes = [
        "Coordinator can send this payload to /api/prepare",
        "If simulate_crash_before_vote=true, coordinator should treat it as timeout/unknown vote",
    ]
    if request.simulate_delay_ms > 0:
        notes.append(f"Simulated delay configured: {request.simulate_delay_ms}ms")

    timeout = max(3000, request.simulate_delay_ms + 2000)
    return CoordinatorPreparePayloadResponse(
        transaction_id=request.transaction_id,
        participant="bank-1-participant",
        prepare_endpoint="/api/prepare",
        payload={
            "transaction_id": request.transaction_id,
            "account_id": request.account_id,
            "operation": request.operation.value,
            "amount": request.amount,
            "simulate_delay_ms": request.simulate_delay_ms,
            "simulate_crash_before_vote": request.simulate_crash_before_vote,
        },
        suggested_timeout_ms=timeout,
        notes=notes,
    )
