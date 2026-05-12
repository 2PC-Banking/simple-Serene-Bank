"""Commit API - Endpoint cho COMMIT phase của 2PC."""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.commit_schema import CommitRequest, CommitResponse
from app.services.transaction_service import TransactionService
from app.utils.logger import log_error, log_transaction
from app.models.transaction_model import TransactionLog
from app.api.simulation import get_current_receiver_simulation

router = APIRouter(prefix="/api", tags=["2PC - Commit"])


@router.post("/commit", response_model=CommitResponse)
def commit(request: CommitRequest, db: Session = Depends(get_db)):
    """
    COMMIT Phase (Phase 2) của Two-Phase Commit.
    
    Coordinator nhận đủ vote YES → gửi COMMIT.
    Participant thực hiện:
    - Apply thay đổi balance (DEBIT/CREDIT)
    - Cập nhật status → COMMITTED
    - Unlock tài khoản

    Nếu simulate_crash=True: commit thật vào DB nhưng trả lỗi 500
    để giả lập coordinator không nhận được response (Phase 2 crash).
    """
    try:
        tx = db.query(TransactionLog).filter(TransactionLog.transaction_id == request.transaction_id).first()
        if tx and tx.operation == "CREDIT":
            sim = get_current_receiver_simulation()
            request.simulate_delay_ms = max(request.simulate_delay_ms, sim.simulate_delay_ms)
            if sim.simulate_commit_fail_before_apply:
                request.simulate_fail_before_apply = True
            if sim.simulate_commit_crash:
                request.simulate_crash = True

        if request.simulate_delay_ms > 0:
            log_transaction(
                request.transaction_id,
                "COMMIT",
                f"Simulating delay {request.simulate_delay_ms}ms before apply",
            )
            time.sleep(request.simulate_delay_ms / 1000)

        if request.simulate_fail_before_apply:
            log_error(
                request.transaction_id,
                "COMMIT",
                "Simulated failure before apply commit",
            )
            raise HTTPException(
                status_code=500,
                detail="Phase 2 exception simulated: failed before applying COMMIT",
            )

        result = TransactionService.commit(
            db=db,
            transaction_id=request.transaction_id,
        )

        # Simulate crash: DB đã commit thật, nhưng trả lỗi
        # → Coordinator không biết đã commit hay chưa → cần recovery
        if request.simulate_crash:
            log_error(request.transaction_id, "COMMIT",
                      "💥 SIMULATED CRASH after commit! DB committed but response lost.")
            raise HTTPException(
                status_code=500,
                detail=f"💥 CRASH SIMULATED: Transaction '{request.transaction_id}' committed in DB but "
                       f"coordinator lost connection! This simulates a Phase 2 crash scenario."
            )

        return CommitResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        log_error(request.transaction_id, "COMMIT", str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error during COMMIT: {str(e)}")
