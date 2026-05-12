"""
Transaction Service - Xử lý logic 2PC (Prepare, Commit, Rollback)
"""

from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.account_model import Account
from app.models.transaction_model import TransactionLog
from app.services.lock_service import LockService
from app.utils.logger import log_transaction, log_error
from app.utils.exceptions import (
    AccountNotFoundError,
    AccountLockedError,
    InsufficientBalanceError,
    TransactionNotFoundError,
    TransactionInvalidStateError,
    PrepareFailedError,
)


class TransactionService:
    """Service xử lý giao dịch Two-Phase Commit"""

    # ========================
    # PHASE 1: PREPARE
    # ========================
    @staticmethod
    def prepare(db: Session, transaction_id: str, account_id: str, operation: str, amount: float) -> dict:
        """
        PREPARE phase: Kiểm tra điều kiện, lock tài khoản, ghi transaction log.
        
        Steps:
        1. Kiểm tra tài khoản tồn tại
        2. Kiểm tra tài khoản chưa bị khóa
        3. Nếu DEBIT: kiểm tra đủ số dư
        4. Lock tài khoản
        5. Ghi transaction_log với status = PREPARED
        6. Trả vote YES
        """
        log_transaction(transaction_id, "PREPARE", f"Starting for account={account_id}, op={operation}, amount={amount}")

        # 1. Kiểm tra tài khoản tồn tại
        account = db.query(Account).filter(Account.account_id == account_id).with_for_update().first()
        if account is None:
            log_error(transaction_id, "PREPARE", f"Account '{account_id}' not found")
            raise AccountNotFoundError(account_id)

        # 2. Kiểm tra tài khoản chưa bị khóa bởi TX khác
        if account.is_locked and account.locked_by_tx != transaction_id:
            log_error(transaction_id, "PREPARE", f"Account '{account_id}' locked by '{account.locked_by_tx}'")
            raise AccountLockedError(account_id, account.locked_by_tx)

        # 3. Nếu DEBIT, kiểm tra đủ số dư
        if operation == "DEBIT":
            if float(account.balance) < amount:
                log_error(transaction_id, "PREPARE", f"Insufficient balance: {account.balance} < {amount}")
                raise InsufficientBalanceError(account_id, float(account.balance), amount)

        # 4. Check for idempotent repeat (already PREPARED by this TX)
        existing = db.query(TransactionLog).filter(
            TransactionLog.transaction_id == transaction_id,
            TransactionLog.account_id == account_id,
            TransactionLog.status == "PREPARED"
        ).first()

        if existing:
            log_transaction(transaction_id, "PREPARE", "Already prepared (idempotent)")
            return {
                "transaction_id": transaction_id,
                "vote": "YES",
                "message": "Already prepared (idempotent)",
                "account_id": account_id,
                "operation": operation,
                "amount": amount,
            }

        # 5. Lock account via LockService (uses SELECT FOR UPDATE internally)
        locked = LockService.lock_account(db=db, account_id=account_id, transaction_id=transaction_id)
        if not locked:
            log_error(transaction_id, "PREPARE", f"Failed to acquire lock on account '{account_id}'")
            raise AccountLockedError(account_id, account.locked_by_tx or "unknown")

        # 6. Write transaction log
        tx_log = TransactionLog(
            transaction_id=transaction_id,
            account_id=account_id,
            operation=operation,
            amount=Decimal(str(amount)),
            status="PREPARED"
        )
        db.add(tx_log)
        db.commit()

        log_transaction(transaction_id, "PREPARE", f"Vote: YES — account '{account_id}' locked and ready")

        return {
            "transaction_id": transaction_id,
            "vote": "YES",
            "message": f"Prepare successful. Account '{account_id}' locked and ready.",
            "account_id": account_id,
            "operation": operation,
            "amount": amount,
        }


    # ========================
    # PHASE 2: COMMIT
    # ========================
    @staticmethod
    def commit(db: Session, transaction_id: str) -> dict:
        """
        COMMIT phase: Thực hiện thay đổi balance, unlock tài khoản.
        
        Steps:
        1. Tìm transaction log với status = PREPARED
        2. Thực hiện DEBIT/CREDIT trên balance
        3. Cập nhật status → COMMITTED
        4. Unlock tài khoản
        """
        log_transaction(transaction_id, "COMMIT", "Starting commit phase")

        # 1. Tìm transaction log PREPARED
        tx_log = db.query(TransactionLog).filter(
            TransactionLog.transaction_id == transaction_id,
            TransactionLog.status == "PREPARED"
        ).first()

        if tx_log is None:
            # Kiểm tra đã committed chưa (idempotent)
            committed = db.query(TransactionLog).filter(
                TransactionLog.transaction_id == transaction_id,
                TransactionLog.status == "COMMITTED"
            ).first()

            if committed:
                account = db.query(Account).filter(Account.account_id == committed.account_id).first()
                log_transaction(transaction_id, "COMMIT", "Already committed (idempotent)")
                return {
                    "transaction_id": transaction_id,
                    "status": "COMMITTED",
                    "message": "Already committed (idempotent)",
                    "account_id": committed.account_id,
                    "operation": committed.operation,
                    "amount": float(committed.amount),
                    "new_balance": float(account.balance) if account else 0,
                }

            log_error(transaction_id, "COMMIT", "No PREPARED transaction found")
            raise TransactionNotFoundError(transaction_id)

        # 2. Lấy account và thực hiện thay đổi balance
        account = db.query(Account).filter(
            Account.account_id == tx_log.account_id
        ).with_for_update().first()

        if account is None:
            log_error(transaction_id, "COMMIT", f"Account '{tx_log.account_id}' not found")
            raise AccountNotFoundError(tx_log.account_id)

        if tx_log.operation == "DEBIT":
            account.balance = account.balance - tx_log.amount
        elif tx_log.operation == "CREDIT":
            account.balance = account.balance + tx_log.amount

        # 3. Cập nhật status → COMMITTED
        tx_log.status = "COMMITTED"

        # 4. Unlock tài khoản
        account.is_locked = False
        account.locked_by_tx = None

        db.commit()

        new_balance = float(account.balance)
        log_transaction(transaction_id, "COMMIT",
                        f"Committed — {tx_log.operation} {tx_log.amount} on '{tx_log.account_id}', new balance: {new_balance}")

        return {
            "transaction_id": transaction_id,
            "status": "COMMITTED",
            "message": f"Transaction committed. {tx_log.operation} {float(tx_log.amount):,.2f} on account '{tx_log.account_id}'.",
            "account_id": tx_log.account_id,
            "operation": tx_log.operation,
            "amount": float(tx_log.amount),
            "new_balance": new_balance,
        }

    # ========================
    # PHASE 2 (ALT): ROLLBACK
    # ========================
    @staticmethod
    def rollback(db: Session, transaction_id: str) -> dict:
        """
        ROLLBACK phase: Hủy transaction, unlock tài khoản.
        
        Steps:
        1. Tìm transaction log
        2a. Nếu PREPARED/INIT → Abort và unlock (chưa apply balance thật)
        2b. Nếu COMMITTED → Tạo compensating transaction đảo ngược balance (force rollback sau timeout)
        3. Trả về ABORTED
        """
        log_transaction(transaction_id, "ROLLBACK", "Starting rollback phase")

        # 1. Tìm transaction log
        tx_log = db.query(TransactionLog).filter(
            TransactionLog.transaction_id == transaction_id,
            TransactionLog.status.in_(["PREPARED", "INIT"])
        ).first()

        if tx_log is None:
            # Kiểm tra đã COMMITTED chưa
            committed = db.query(TransactionLog).filter(
                TransactionLog.transaction_id == transaction_id,
                TransactionLog.status == "COMMITTED"
            ).first()
            if committed:
                # ── COMPENSATING ROLLBACK ──────────────────────────────────────────
                # Coordinator force rollback sau timeout Phase 2.
                # Giao dịch đã apply balance thật → cần đảo ngược.
                log_transaction(transaction_id, "COMPENSATE_ROLLBACK",
                                f"Coordinator forced ROLLBACK after timeout. Creating compensating transaction.")

                account = db.query(Account).filter(
                    Account.account_id == committed.account_id
                ).with_for_update().first()

                if account is None:
                    log_error(transaction_id, "COMPENSATE_ROLLBACK", f"Account '{committed.account_id}' not found")
                    raise AccountNotFoundError(committed.account_id)

                # Đảo ngược: CREDIT đã nhận → DEBIT lại, DEBIT đã trừ → CREDIT lại
                comp_operation = "DEBIT" if committed.operation == "CREDIT" else "CREDIT"
                if committed.operation == "CREDIT":
                    account.balance = account.balance - committed.amount  # Trừ lại tiền đã credit nhầm
                elif committed.operation == "DEBIT":
                    account.balance = account.balance + committed.amount  # Hoàn lại tiền đã debit

                # Unlock tài khoản
                account.is_locked = False
                account.locked_by_tx = None

                # Đánh dấu log → ABORTED (compensated)
                committed.status = "ABORTED"
                
                # Tạo giao dịch mới để ghi nhận việc bù trừ
                compensate_tx = TransactionLog(
                    transaction_id=f"{transaction_id}_COMPENSATE",
                    account_id=committed.account_id,
                    operation=comp_operation,
                    amount=committed.amount,
                    status="COMMITTED"
                )
                db.add(compensate_tx)
                
                db.commit()

                new_balance = float(account.balance)
                log_transaction(transaction_id, "COMPENSATE_ROLLBACK",
                                f"Balance reversed: {committed.operation} of {committed.amount} reversed. New balance: {new_balance}")

                return {
                    "transaction_id": transaction_id,
                    "status": "ABORTED",
                    "message": f"Compensating rollback applied. {committed.operation} of {float(committed.amount):,.2f} reversed.",
                    "account_id": committed.account_id,
                }

            # Already ABORTED → idempotent
            aborted = db.query(TransactionLog).filter(
                TransactionLog.transaction_id == transaction_id,
                TransactionLog.status == "ABORTED"
            ).first()

            if aborted:
                log_transaction(transaction_id, "ROLLBACK", "Already aborted (idempotent)")
                return {
                    "transaction_id": transaction_id,
                    "status": "ABORTED",
                    "message": "Already aborted (idempotent)",
                    "account_id": aborted.account_id,
                }

            log_error(transaction_id, "ROLLBACK", "No PREPARED/INIT transaction found")
            raise TransactionNotFoundError(transaction_id)


        account_id = tx_log.account_id

        # 2. Update status → ABORTED
        tx_log.status = "ABORTED"

        # 3. Unlock account via LockService
        LockService.unlock_account(db=db, account_id=account_id, transaction_id=transaction_id)

        db.commit()

        log_transaction(transaction_id, "ROLLBACK", f"Aborted — account '{account_id}' unlocked")

        return {
            "transaction_id": transaction_id,
            "status": "ABORTED",
            "message": f"Transaction rolled back. Account '{account_id}' unlocked.",
            "account_id": account_id,
        }

