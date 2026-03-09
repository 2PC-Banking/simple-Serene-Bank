"""
Prepare API - Endpoint cho PREPARE phase của 2PC
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.prepare_schema import PrepareRequest, PrepareResponse
from app.services.transaction_service import TransactionService
from app.utils.logger import log_transaction, log_error

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
        raise HTTPException(status_code=500, detail=f"Internal error during PREPARE: {str(e)}")
