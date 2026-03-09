"""
Balance API - Endpoint xem thông tin tài khoản và số dư
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.account_model import Account
from app.models.transaction_model import TransactionLog

router = APIRouter(prefix="/api", tags=["Balance"])


@router.get("/accounts")
def get_all_accounts(db: Session = Depends(get_db)):
    """Lấy danh sách tất cả tài khoản"""
    accounts = db.query(Account).all()
    return {
        "status": "success",
        "count": len(accounts),
        "data": [acc.to_dict() for acc in accounts]
    }


@router.get("/accounts/{account_id}")
def get_account(account_id: str, db: Session = Depends(get_db)):
    """Lấy thông tin một tài khoản theo ID"""
    account = db.query(Account).filter(Account.account_id == account_id).first()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account '{account_id}' not found"
        )
    return {
        "status": "success",
        "data": account.to_dict()
    }


@router.get("/accounts/{account_id}/balance")
def get_balance(account_id: str, db: Session = Depends(get_db)):
    """Lấy số dư của tài khoản"""
    account = db.query(Account).filter(Account.account_id == account_id).first()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account '{account_id}' not found"
        )
    return {
        "status": "success",
        "account_id": account.account_id,
        "account_name": account.account_name,
        "balance": float(account.balance),
        "is_locked": account.is_locked,
        "locked_by_tx": account.locked_by_tx
    }


@router.get("/transactions")
def get_all_transactions(
    status_filter: str = None,
    account_id: str = None,
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách transaction log.
    Có thể filter theo status và account_id.
    """
    query = db.query(TransactionLog)

    if status_filter:
        query = query.filter(TransactionLog.status == status_filter.upper())
    if account_id:
        query = query.filter(TransactionLog.account_id == account_id)

    transactions = query.order_by(TransactionLog.created_at.desc()).all()
    return {
        "status": "success",
        "count": len(transactions),
        "data": [tx.to_dict() for tx in transactions]
    }


@router.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Lấy thông tin transaction theo transaction_id"""
    tx_logs = db.query(TransactionLog).filter(
        TransactionLog.transaction_id == transaction_id
    ).all()

    if not tx_logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found"
        )

    return {
        "status": "success",
        "transaction_id": transaction_id,
        "data": [tx.to_dict() for tx in tx_logs]
    }
