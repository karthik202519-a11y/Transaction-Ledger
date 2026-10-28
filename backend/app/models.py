from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def identifier():
    return str(uuid4())


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    balance_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=timestamp)
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 120", name="valid_account_name"),
        CheckConstraint("typeof(balance_cents) = 'integer' AND balance_cents BETWEEN 0 AND 999999999999", name="valid_balance"),
    )


class Transaction(Base):
    __tablename__ = "transactions"
    # Sequence is an internal deterministic tie-breaker, never a client field.
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, default=identifier)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    type: Mapped[str] = mapped_column(String(6), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    reference_id: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=timestamp)
    transfer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    __table_args__ = (
        UniqueConstraint("account_id", "reference_id", name="unique_account_reference"),
        CheckConstraint("type IN ('credit', 'debit')", name="valid_transaction_type"),
        CheckConstraint("typeof(amount_cents) = 'integer' AND amount_cents BETWEEN 1 AND 999999999999", name="valid_amount"),
        CheckConstraint("length(trim(reference_id)) BETWEEN 1 AND 120", name="valid_reference"),
        CheckConstraint("length(description) <= 500", name="valid_description"),
        Index("ix_history", "account_id", "created_at", "sequence"),
    )
