"""
Transaction Log Model - SQLAlchemy ORM model for transaction_log table
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class TransactionLog(Base):
    __tablename__ = "transaction_log"
    __table_args__ = {"schema": "dbo"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(100), nullable=False)
    account_id = Column(String(50), ForeignKey("dbo.accounts.account_id"), nullable=False)
    operation = Column(String(20), nullable=False)  # 'DEBIT' or 'CREDIT'
    amount = Column(Numeric(18, 2), nullable=False)
    status = Column(String(20), nullable=False, default="INIT")  # INIT, PREPARED, COMMITTED, ABORTED
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TransactionLog(tx={self.transaction_id}, acc={self.account_id}, op={self.operation}, status={self.status})>"

    def to_dict(self):
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "account_id": self.account_id,
            "operation": self.operation,
            "amount": float(self.amount),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
