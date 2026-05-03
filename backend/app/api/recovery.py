"""
Recovery API - Endpoints for 2PC recovery operations.
Handles pending transaction inspection and cleanup after participant crash/restart.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional

from app.services.recovery_service import RecoveryService

router = APIRouter(prefix="/api/recovery", tags=["2PC - Recovery"])


# ── Response Schemas ──────────────────────────────────────────────────────────

class PendingTransactionDetail(BaseModel):
    transaction_id: str
    account_id: str
    operation: str
    amount: float
    status: str
    created_at: Optional[str] = None


class PendingStatusResponse(BaseModel):
    pending_count: int
    message: str
    details: List[PendingTransactionDetail] = Field(default_factory=list)


class RolledBackDetail(BaseModel):
    transaction_id: str
    account_id: str
    operation: str
    age_seconds: Optional[float] = None


class ForceRollbackResponse(BaseModel):
    rolled_back_count: int
    transaction_ids: List[str]
    details: Optional[List[RolledBackDetail]] = None


class CleanedLockDetail(BaseModel):
    account_id: str
    was_locked_by: str


class CleanupLocksResponse(BaseModel):
    cleaned_count: int
    details: List[CleanedLockDetail] = Field(default_factory=list)


class AutoRollbackResponse(BaseModel):
    rolled_back_count: int
    transaction_ids: List[str]
    timeout_seconds: int
    details: Optional[List[RolledBackDetail]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/pending", response_model=PendingStatusResponse)
def list_pending_transactions():
    """
    List all transactions currently stuck in PREPARED state.

    These are transactions that have completed Phase 1 but not received
    a COMMIT or ROLLBACK decision from the coordinator. Common after
    coordinator crash or network partition.
    """
    result = RecoveryService.list_pending_transactions()
    count = result["pending"]
    return PendingStatusResponse(
        pending_count=count,
        message=f"{count} transaction(s) pending coordinator decision." if count else "No pending transactions.",
        details=[PendingTransactionDetail(**d) for d in result["details"]],
    )


@router.post("/force-rollback", response_model=ForceRollbackResponse)
def force_rollback_all():
    """
    Force-rollback ALL transactions currently in PREPARED state.

    Use this for emergency cleanup when the coordinator is confirmed dead
    and you need to release all account locks immediately.

    ⚠ This is a destructive operation – any in-flight transaction
    that was waiting for COMMIT will be permanently aborted.
    """
    result = RecoveryService.force_rollback_all_prepared()
    details = [RolledBackDetail(**d) for d in result.get("details", [])] if result.get("details") else None
    return ForceRollbackResponse(
        rolled_back_count=result["rolled_back_count"],
        transaction_ids=result["transaction_ids"],
        details=details,
    )


@router.post("/auto-rollback-expired", response_model=AutoRollbackResponse)
def auto_rollback_expired():
    """
    Auto-rollback PREPARED transactions that have exceeded the lock timeout.

    Uses LOCK_TIMEOUT from server config (default 30 s).
    Safe to call periodically – only affects transactions past the deadline.
    """
    result = RecoveryService.auto_rollback_expired()
    details = [RolledBackDetail(**d) for d in result.get("details", [])] if result.get("details") else None
    return AutoRollbackResponse(
        rolled_back_count=result["rolled_back_count"],
        transaction_ids=result["transaction_ids"],
        timeout_seconds=result["timeout_seconds"],
        details=details,
    )


@router.post("/cleanup-locks", response_model=CleanupLocksResponse)
def cleanup_stale_locks():
    """
    Remove stale account locks that have no corresponding PREPARED transaction.

    This can happen when a transaction record was deleted manually or the DB
    state became inconsistent. Safe to run at any time.
    """
    result = RecoveryService.cleanup_stale_locks()
    return CleanupLocksResponse(
        cleaned_count=result["cleaned_count"],
        details=[CleanedLockDetail(**d) for d in result["details"]],
    )
