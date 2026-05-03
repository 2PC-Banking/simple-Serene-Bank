"""
Prepare Schema - Request/Response models for PREPARE phase
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class OperationType(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class PrepareRequest(BaseModel):
    """Request body cho PREPARE phase"""
    transaction_id: str = Field(..., description="Global Transaction ID từ Coordinator", examples=["TX-2024-001"])
    account_id: str = Field(..., description="ID tài khoản cần thao tác", examples=["ACC001"])
    operation: OperationType = Field(..., description="Loại thao tác: DEBIT hoặc CREDIT")
    amount: float = Field(..., gt=0, description="Số tiền giao dịch (phải > 0)", examples=[100000.00])
    simulate_delay_ms: int = Field(0, ge=0, le=15000, description="Delay trước khi xử lý PREPARE (ms)")
    simulate_crash_before_vote: bool = Field(False, description="Giả lập crash trước khi participant trả vote")


class PrepareResponse(BaseModel):
    """Response body cho PREPARE phase"""
    transaction_id: str = Field(..., description="Transaction ID")
    vote: str = Field(..., description="YES nếu prepare thành công, NO nếu thất bại")
    message: str = Field(..., description="Thông báo chi tiết")
    account_id: str = Field(..., description="ID tài khoản")
    operation: str = Field(..., description="Loại thao tác")
    amount: float = Field(..., description="Số tiền giao dịch")


class CoordinatorPreparePayloadResponse(BaseModel):
    """Preview payload để frontend/coordinator gửi PREPARE"""
    transaction_id: str = Field(..., description="Transaction ID")
    participant: str = Field(..., description="Participant service name")
    prepare_endpoint: str = Field(..., description="Endpoint nhận PREPARE")
    payload: dict = Field(..., description="Payload chuẩn hóa để coordinator gửi")
    suggested_timeout_ms: int = Field(..., description="Timeout khuyến nghị cho coordinator")
    notes: list[str] = Field(..., description="Ghi chú về các case mô phỏng")
