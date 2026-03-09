"""
Single Bank API - Simplified endpoints for testing single participant
Dùng để test 1 bank riêng lẻ trong mô hình 2PC
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

from app.core.database import get_db
from app.services.transaction_service import TransactionService
from app.models.account_model import Account
from app.models.transaction_model import TransactionLog

router = APIRouter(prefix="/api/single", tags=["Single Bank Operations"])


class OperationType(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class SingleTransactionRequest(BaseModel):
    """Request cho giao dịch đơn (1 bank)"""
    account_id: str = Field(..., description="ID tài khoản", examples=["ACC001"])
    operation: OperationType = Field(..., description="DEBIT (trừ) hoặc CREDIT (cộng)")
    amount: float = Field(..., gt=0, description="Số tiền > 0", examples=[100000])


class SingleTransactionResponse(BaseModel):
    """Response cho giao dịch đơn"""
    transaction_id: str
    account_id: str
    operation: str
    amount: float
    old_balance: float
    new_balance: float
    status: str
    message: str


class Full2PCRequest(BaseModel):
    """Request cho full 2PC flow trong 1 call"""
    transaction_id: Optional[str] = Field(None, description="TX ID (auto-generate nếu không có)")
    account_id: str = Field(..., description="ID tài khoản")
    operation: OperationType = Field(..., description="DEBIT hoặc CREDIT")
    amount: float = Field(..., gt=0, description="Số tiền")


@router.post("/transfer", response_model=SingleTransactionResponse)
def single_transfer(request: SingleTransactionRequest, db: Session = Depends(get_db)):
    """
    Thực hiện giao dịch đơn giản trên 1 tài khoản.

    Đây là shortcut để test - tự động chạy full 2PC flow:
    1. Generate transaction ID
    2. PREPARE
    3. COMMIT (nếu prepare thành công)

    Trong thực tế, Coordinator sẽ điều phối các bước này.
    """
    import uuid
    tx_id = f"TX-AUTO-{uuid.uuid4().hex[:8].upper()}"

    # Lấy số dư cũ
    account = db.query(Account).filter(Account.account_id == request.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account '{request.account_id}' not found")

    old_balance = float(account.balance)

    try:
        # Phase 1: PREPARE
        prepare_result = TransactionService.prepare(
            db=db,
            transaction_id=tx_id,
            account_id=request.account_id,
            operation=request.operation.value,
            amount=request.amount
        )

        if prepare_result["vote"] != "YES":
            raise HTTPException(status_code=400, detail="Prepare failed")

        # Phase 2: COMMIT
        commit_result = TransactionService.commit(
            db=db,
            transaction_id=tx_id
        )

        return SingleTransactionResponse(
            transaction_id=tx_id,
            account_id=request.account_id,
            operation=request.operation.value,
            amount=request.amount,
            old_balance=old_balance,
            new_balance=commit_result["new_balance"],
            status="SUCCESS",
            message=f"{request.operation.value} {request.amount:,.0f} VND thành công"
        )

    except HTTPException:
        # Rollback nếu có lỗi
        try:
            TransactionService.rollback(db=db, transaction_id=tx_id)
        except:
            pass
        raise
    except Exception as e:
        # Rollback và raise error
        try:
            TransactionService.rollback(db=db, transaction_id=tx_id)
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/full-2pc")
def full_2pc_single_account(request: Full2PCRequest, db: Session = Depends(get_db)):
    """
    Chạy full 2PC flow cho 1 account với log chi tiết từng phase.

    Trả về chi tiết từng bước để dễ debug và hiểu flow.
    """
    import uuid
    tx_id = request.transaction_id or f"TX-2PC-{uuid.uuid4().hex[:8].upper()}"

    result = {
        "transaction_id": tx_id,
        "account_id": request.account_id,
        "operation": request.operation.value,
        "amount": request.amount,
        "phases": []
    }

    # Lấy thông tin account ban đầu
    account = db.query(Account).filter(Account.account_id == request.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account '{request.account_id}' not found")

    initial_balance = float(account.balance)
    result["initial_balance"] = initial_balance

    # ===== PHASE 1: PREPARE =====
    prepare_phase = {
        "phase": "PREPARE",
        "status": None,
        "vote": None,
        "details": {}
    }

    try:
        prepare_result = TransactionService.prepare(
            db=db,
            transaction_id=tx_id,
            account_id=request.account_id,
            operation=request.operation.value,
            amount=request.amount
        )
        prepare_phase["status"] = "SUCCESS"
        prepare_phase["vote"] = prepare_result["vote"]
        prepare_phase["details"] = prepare_result
        result["phases"].append(prepare_phase)

    except HTTPException as e:
        prepare_phase["status"] = "FAILED"
        prepare_phase["vote"] = "NO"
        prepare_phase["details"] = {"error": e.detail}
        result["phases"].append(prepare_phase)
        result["final_status"] = "ABORTED"
        result["final_balance"] = initial_balance
        result["message"] = f"PREPARE failed: {e.detail}"
        return result

    # ===== PHASE 2: COMMIT =====
    commit_phase = {
        "phase": "COMMIT",
        "status": None,
        "details": {}
    }

    try:
        commit_result = TransactionService.commit(
            db=db,
            transaction_id=tx_id
        )
        commit_phase["status"] = "SUCCESS"
        commit_phase["details"] = commit_result
        result["phases"].append(commit_phase)

        result["final_status"] = "COMMITTED"
        result["final_balance"] = commit_result["new_balance"]
        result["balance_change"] = commit_result["new_balance"] - initial_balance
        result["message"] = f"Transaction committed successfully. {request.operation.value} {request.amount:,.0f} VND"

    except Exception as e:
        commit_phase["status"] = "FAILED"
        commit_phase["details"] = {"error": str(e)}
        result["phases"].append(commit_phase)

        # Attempt rollback
        try:
            TransactionService.rollback(db=db, transaction_id=tx_id)
            result["phases"].append({
                "phase": "ROLLBACK",
                "status": "SUCCESS",
                "details": {"reason": "Commit failed, rolled back"}
            })
        except:
            pass

        result["final_status"] = "ABORTED"
        result["final_balance"] = initial_balance
        result["message"] = f"COMMIT failed: {str(e)}"

    return result


@router.get("/status/{transaction_id}")
def get_single_transaction_status(transaction_id: str, db: Session = Depends(get_db)):
    """
    Xem trạng thái của 1 transaction.
    """
    tx_logs = db.query(TransactionLog).filter(
        TransactionLog.transaction_id == transaction_id
    ).all()

    if not tx_logs:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")

    tx = tx_logs[0]
    account = db.query(Account).filter(Account.account_id == tx.account_id).first()

    return {
        "transaction_id": transaction_id,
        "account_id": tx.account_id,
        "operation": tx.operation,
        "amount": float(tx.amount),
        "status": tx.status,
        "current_balance": float(account.balance) if account else None,
        "account_locked": account.is_locked if account else None,
        "locked_by": account.locked_by_tx if account else None,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
        "updated_at": tx.updated_at.isoformat() if tx.updated_at else None,
    }


@router.post("/reset-account/{account_id}")
def reset_account_balance(
    account_id: str,
    new_balance: float = 10000000.00,
    db: Session = Depends(get_db)
):
    """
    Reset số dư tài khoản về giá trị mặc định (dùng cho testing).
    Cũng unlock account nếu đang bị lock.
    """
    account = db.query(Account).filter(Account.account_id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")

    old_balance = float(account.balance)
    was_locked = account.is_locked

    account.balance = new_balance
    account.is_locked = False
    account.locked_by_tx = None
    db.commit()

    return {
        "account_id": account_id,
        "old_balance": old_balance,
        "new_balance": new_balance,
        "was_locked": was_locked,
        "message": f"Account reset to {new_balance:,.0f} VND"
    }


@router.post("/simulate-crash/{transaction_id}")
def simulate_crash_after_prepare(transaction_id: str, db: Session = Depends(get_db)):
    """
    Giả lập crash sau PREPARE (transaction stuck ở PREPARED state).
    Dùng để test recovery flow.

    Transaction sẽ ở trạng thái PREPARED và account bị locked.
    """
    tx = db.query(TransactionLog).filter(
        TransactionLog.transaction_id == transaction_id,
        TransactionLog.status == "PREPARED"
    ).first()

    if not tx:
        raise HTTPException(
            status_code=404,
            detail=f"No PREPARED transaction found with ID '{transaction_id}'"
        )

    return {
        "message": "Simulated crash - transaction left in PREPARED state",
        "transaction_id": transaction_id,
        "account_id": tx.account_id,
        "status": "PREPARED",
        "note": "Use /api/recovery/status to see pending transactions, /api/recovery/force-rollback to cleanup"
    }


