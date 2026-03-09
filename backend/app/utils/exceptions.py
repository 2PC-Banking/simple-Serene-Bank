"""
Custom exceptions for Bank System 2PC
"""

from fastapi import HTTPException, status


class AccountNotFoundError(HTTPException):
    """Tài khoản không tồn tại"""
    def __init__(self, account_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account '{account_id}' not found"
        )


class AccountLockedError(HTTPException):
    """Tài khoản đang bị khóa bởi transaction khác"""
    def __init__(self, account_id: str, locked_by: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account '{account_id}' is locked by transaction '{locked_by}'"
        )


class InsufficientBalanceError(HTTPException):
    """Số dư không đủ"""
    def __init__(self, account_id: str, balance: float, amount: float):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance for account '{account_id}': balance={balance}, required={amount}"
        )


class TransactionNotFoundError(HTTPException):
    """Transaction không tồn tại"""
    def __init__(self, transaction_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found"
        )


class TransactionInvalidStateError(HTTPException):
    """Transaction ở trạng thái không hợp lệ cho thao tác"""
    def __init__(self, transaction_id: str, current_status: str, expected_status: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transaction '{transaction_id}' is in state '{current_status}', expected '{expected_status}'"
        )


class PrepareFailedError(HTTPException):
    """Prepare phase thất bại"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PREPARE failed: {detail}"
        )
