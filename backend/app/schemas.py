from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
MAX_CENTS = 999_999_999_999


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateAccount(Input):
    name: Name


class MoneyInput(Input):
    amount: Decimal = Field(gt=0, le=Decimal("9999999999.99"), allow_inf_nan=False)
    reference_id: Reference
    description: str = Field(default="", max_length=500)

    @field_validator("amount", mode="before")
    @classmethod
    def reject_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("Amount must be a number, not a boolean")
        return value

    @field_validator("amount")
    @classmethod
    def exact_cents(cls, value):
        # Arithmetic uses Decimal's finite context and can round long inputs BEFORE
        # validation. Inspect the exact coefficient instead, without multiplying,
        # normalizing, quantizing, or expanding a potentially enormous exponent.
        _, digits, exponent = value.as_tuple()
        fractional_digits_beyond_cents = max(0, -exponent - 2)
        if fractional_digits_beyond_cents and any(digits[-fractional_digits_beyond_cents:]):
            raise ValueError("Amount must have at most two decimal places")
        return value


class CreateTransaction(MoneyInput):
    type: Literal["credit", "debit"]


class CreateTransfer(MoneyInput):
    source_account_id: UUID
    destination_account_id: UUID


class AccountOut(BaseModel):
    id: str
    name: str
    balance: str
    created_at: str


class BalanceOut(BaseModel):
    account_id: str
    balance: str


class TransactionOut(BaseModel):
    id: str
    account_id: str
    type: Literal["credit", "debit"]
    amount: str
    description: str
    reference_id: str
    created_at: str
    transfer_id: str | None


class HistoryOut(BaseModel):
    items: list[TransactionOut]
    current_page: int
    page_size: int
    total_records: int
    total_pages: int


class TransferOut(BaseModel):
    transfer_id: str
    source_balance: str
    destination_balance: str
    debit: TransactionOut
    credit: TransactionOut


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail]


class ErrorOut(BaseModel):
    error: ErrorBody
