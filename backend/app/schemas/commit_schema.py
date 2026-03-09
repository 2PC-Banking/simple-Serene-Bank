"""
Commit Schema - Request/Response models for COMMIT phase
"""

from pydantic import BaseModel, Field


class CommitRequest(BaseModel):
    """Request body cho COMMIT phase"""
    transaction_id: str = Field(..., description="Global Transaction ID cần commit", examples=["TX-2024-001"])
    simulate_crash: bool = Field(False, description="Simulate crash during commit (Phase 2 crash test)")


class CommitResponse(BaseModel):
    """Response body cho COMMIT phase"""
    transaction_id: str = Field(..., description="Transaction ID")
    status: str = Field(..., description="COMMITTED nếu thành công")
    message: str = Field(..., description="Thông báo chi tiết")
    account_id: str = Field(..., description="ID tài khoản đã cập nhật")
    operation: str = Field(..., description="Loại thao tác đã thực hiện")
    amount: float = Field(..., description="Số tiền đã giao dịch")
    new_balance: float = Field(..., description="Số dư mới sau giao dịch")
