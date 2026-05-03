"""
Rollback Schema - Request/Response models for ROLLBACK phase
"""

from pydantic import BaseModel, Field


class RollbackRequest(BaseModel):
    """Request body cho ROLLBACK phase"""
    transaction_id: str = Field(..., description="Global Transaction ID cần rollback", examples=["TX-2024-001"])
    simulate_delay_ms: int = Field(0, ge=0, le=15000, description="Delay trước khi xử lý ROLLBACK (ms)")
    simulate_crash_before_apply: bool = Field(False, description="Giả lập crash trước khi apply ROLLBACK")
    simulate_crash_after_apply: bool = Field(False, description="Giả lập mất ACK sau khi rollback đã apply")


class RollbackResponse(BaseModel):
    """Response body cho ROLLBACK phase"""
    transaction_id: str = Field(..., description="Transaction ID")
    status: str = Field(..., description="ABORTED nếu rollback thành công")
    message: str = Field(..., description="Thông báo chi tiết")
    account_id: str = Field(..., description="ID tài khoản đã unlock")
