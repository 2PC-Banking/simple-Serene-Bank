"""
Rollback Schema - Request/Response models for ROLLBACK phase
"""

from pydantic import BaseModel, Field


class RollbackRequest(BaseModel):
    """Request body cho ROLLBACK phase"""
    transaction_id: str = Field(..., description="Global Transaction ID cần rollback", examples=["TX-2024-001"])


class RollbackResponse(BaseModel):
    """Response body cho ROLLBACK phase"""
    transaction_id: str = Field(..., description="Transaction ID")
    status: str = Field(..., description="ABORTED nếu rollback thành công")
    message: str = Field(..., description="Thông báo chi tiết")
    account_id: str = Field(..., description="ID tài khoản đã unlock")
