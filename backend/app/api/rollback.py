"""Rollback API - ROLLBACK phase (Phase 2 alternative) of Two-Phase Commit."""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.rollback_schema import RollbackRequest, RollbackResponse
from app.services.transaction_service import TransactionService
from app.utils.logger import log_error

router = APIRouter(prefix="/api", tags=["2PC - Rollback"])


@router.post("/rollback", response_model=RollbackResponse)
def rollback(request: RollbackRequest, db: Session = Depends(get_db)):
    """
    ROLLBACK Phase (Phase 2 – alternative) of Two-Phase Commit.

    Triggered when coordinator receives at least one NO vote, or when
    a participant fails to respond during Phase 1.

    Participant actions:
    - Update transaction status → ABORTED
    - Unlock the account (no balance change)
    - Return ACK to coordinator

    Idempotent: calling again on an already-ABORTED transaction returns ABORTED.

    Fault simulation flags:
    - simulate_crash_before_apply: participant crashes before writing ABORTED
    - simulate_crash_after_apply:  ABORTED written, but ACK is lost (coordinator sees timeout)
    """
    try:
        if request.simulate_delay_ms > 0:
            time.sleep(request.simulate_delay_ms / 1000)

        if request.simulate_crash_before_apply:
            raise HTTPException(
                status_code=500,
                detail="Fault simulation: participant crashed before applying ROLLBACK",
            )

        result = TransactionService.rollback(
            db=db,
            transaction_id=request.transaction_id,
        )

        if request.simulate_crash_after_apply:
            raise HTTPException(
                status_code=500,
                detail="Fault simulation: ROLLBACK applied in DB but ACK lost (coordinator timeout)",
            )

        return RollbackResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        log_error(request.transaction_id, "ROLLBACK", str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error during ROLLBACK: {str(e)}")
