"""
Commit API - Endpoint cho COMMIT phase của 2PC
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.commit_schema import CommitRequest, CommitResponse
from app.services.transaction_service import TransactionService
from app.utils.logger import log_transaction, log_error

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
