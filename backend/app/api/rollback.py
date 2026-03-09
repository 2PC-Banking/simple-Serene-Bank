"""
Rollback API - Endpoint cho ROLLBACK phase của 2PC
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.rollback_schema import RollbackRequest, RollbackResponse
from app.services.transaction_service import TransactionService
from app.services.recovery_service import RecoveryService
from app.utils.logger import log_transaction, log_error

router = APIRouter(prefix="/api", tags=["2PC - Rollback"])


@router.post("/rollback", response_model=RollbackResponse)
def rollback(request: RollbackRequest, db: Session = Depends(get_db)):
    """
    ROLLBACK Phase (Phase 2 - Alternative) của Two-Phase Commit.
    
    Coordinator nhận ít nhất 1 vote NO → gửi ROLLBACK.
    Participant thực hiện:
    - Cập nhật status → ABORTED
    - Unlock tài khoản
    - Không thay đổi balance
    """
    try:
        result = TransactionService.rollback(
            db=db,
            transaction_id=request.transaction_id,
        )
        return RollbackResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        log_error(request.transaction_id, "ROLLBACK", str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error during ROLLBACK: {str(e)}")


@router.get("/recovery/status")
def recovery_status():
    """Kiểm tra trạng thái các transaction đang pending"""
    result = RecoveryService.recover_pending_transactions()
    return {
        "status": "success",
        **result
    }


@router.post("/recovery/force-rollback")
def force_rollback_all():
    """Force rollback tất cả transaction PREPARED (cleanup)"""
    result = RecoveryService.force_rollback_all_prepared()
    return {
        "status": "success",
        **result
    }


@router.post("/recovery/auto-rollback-expired")
def auto_rollback_expired():
    """Tự động rollback các transaction PREPARED đã quá timeout"""
    result = RecoveryService.auto_rollback_expired()
    return {
        "status": "success",
        **result
    }


@router.post("/recovery/cleanup-locks")
def cleanup_locks():
    """Dọn dẹp các lock cũ không còn transaction tương ứng"""
    result = RecoveryService.cleanup_stale_locks()
    return {
        "status": "success",
        **result
    }
