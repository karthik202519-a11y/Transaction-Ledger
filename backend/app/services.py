from contextlib import contextmanager
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Account, Transaction, identifier, timestamp
from .schemas import MAX_CENTS


class LedgerError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def money(cents: int):
    return f"{cents // 100}.{cents % 100:02d}"


def account_out(account):
    return {"id": account.id, "name": account.name, "balance": money(account.balance_cents), "created_at": account.created_at}


def transaction_out(transaction):
    return {"id": transaction.id, "account_id": transaction.account_id, "type": transaction.type,
            "amount": money(transaction.amount_cents), "description": transaction.description,
            "reference_id": transaction.reference_id, "created_at": transaction.created_at,
            "transfer_id": transaction.transfer_id}


@contextmanager
def write_session(engine):
    with engine.connect().execution_options(sqlite_begin_mode="IMMEDIATE") as connection:
        with connection.begin():
            with Session(bind=connection, expire_on_commit=False) as session:
                yield session
                session.flush()


def require_account(session, account_id):
    account = session.get(Account, str(account_id))
    if account is None:
        raise LedgerError(404, "account_not_found", "Account does not exist.")
    return account


def check_reference(session, account_id, reference):
    existing = session.scalar(select(Transaction.id).where(Transaction.account_id == account_id, Transaction.reference_id == reference))
    if existing:
        raise LedgerError(409, "duplicate_transaction", "This reference ID already exists for the account. Use a new reference for a new transaction.")


def adjust_balance(account, delta):
    new_balance = account.balance_cents + delta
    if new_balance < 0:
        raise LedgerError(409, "insufficient_balance", "The account does not have sufficient balance.")
    if new_balance > MAX_CENTS:
        raise LedgerError(409, "balance_limit_exceeded", "The resulting balance exceeds the supported maximum of 9999999999.99.")
    account.balance_cents = new_balance


def create_account(engine, body):
    with write_session(engine) as session:
        account = Account(name=body.name, balance_cents=0)
        session.add(account)
        session.flush()
        result = account_out(account)
    return result


def post_transaction(engine, account_id, body):
    with write_session(engine) as session:
        account = require_account(session, account_id)
        check_reference(session, account.id, body.reference_id)
        cents = int(body.amount * 100)
        adjust_balance(account, cents if body.type == "credit" else -cents)
        transaction = Transaction(account_id=account.id, type=body.type, amount_cents=cents,
                                  description=body.description, reference_id=body.reference_id)
        session.add(transaction)
        session.flush()
        result = transaction_out(transaction)
    return result


def history(engine, account_id, kind, page, limit):
    with Session(engine) as session:
        account = require_account(session, account_id)
        conditions = [Transaction.account_id == account.id]
        if kind:
            conditions.append(Transaction.type == kind)
        count = session.scalar(select(func.count()).select_from(Transaction).where(*conditions))
        items = session.scalars(select(Transaction).where(*conditions)
                                .order_by(Transaction.created_at.desc(), Transaction.sequence.desc())
                                .offset((page - 1) * limit).limit(limit)).all()
        return {"items": [transaction_out(t) for t in items], "current_page": page,
                "page_size": limit, "total_records": count, "total_pages": ceil(count / limit)}


def transfer(engine, body):
    if body.source_account_id == body.destination_account_id:
        raise LedgerError(422, "same_account", "Choose two different accounts for a transfer.")
    with write_session(engine) as session:
        source = require_account(session, body.source_account_id)
        destination = require_account(session, body.destination_account_id)
        # The submitted reference is reserved on BOTH accounts, in the same transaction.
        check_reference(session, source.id, body.reference_id)
        check_reference(session, destination.id, body.reference_id)
        cents = int(body.amount * 100)
        adjust_balance(source, -cents)
        adjust_balance(destination, cents)
        transfer_id, created_at = identifier(), timestamp()
        entries = [Transaction(account_id=account.id, type=kind, amount_cents=cents,
                    description=body.description, reference_id=body.reference_id,
                    transfer_id=transfer_id, created_at=created_at)
                   for account, kind in [(source, "debit"), (destination, "credit")]]
        session.add_all(entries)
        session.flush()
        result = {"transfer_id": transfer_id, "source_balance": money(source.balance_cents),
                  "destination_balance": money(destination.balance_cents),
                  "debit": transaction_out(entries[0]), "credit": transaction_out(entries[1])}
    return result
