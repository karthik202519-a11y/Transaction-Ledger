import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID

from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from . import schemas, services
from .database import default_database_url, initialize, make_engine
from .models import Account

logger = logging.getLogger(__name__)


def error(status, code, message, details=None):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details or []}})


def create_app(database_url=None):
    engine = make_engine(database_url or os.environ.get("LEDGER_DATABASE_URL") or default_database_url())

    @asynccontextmanager
    async def lifespan(_):
        initialize(engine)
        yield
        engine.dispose()

    app = FastAPI(title="Transaction Ledger API", version="1.0.0", lifespan=lifespan,
                  responses={status: {"model": schemas.ErrorOut, "description": description} for status, description in {
                      404: "Account or route not found", 409: "Duplicate reference, insufficient funds, or integrity conflict",
                      422: "Invalid request", 500: "Unexpected error", 503: "Database busy; retry with the same reference"}.items()},
                  description="Immutable account ledger with exact decimal amounts and atomic transfers. Amounts and balances are decimal strings. No authentication: local assessment only.")
    app.state.engine = engine
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.exception_handler(services.LedgerError)
    async def ledger_error(_, exc):
        return error(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, exc):
        details = [{"field": ".".join(map(str, issue["loc"])), "message": issue["msg"]} for issue in exc.errors()]
        return error(422, "validation_error", "Check the request fields and try again.", details)

    @app.exception_handler(HTTPException)
    async def http_error(_, exc):
        return error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(IntegrityError)
    async def integrity_error(_, exc):
        logger.warning("Database constraint rejected a write: %s", type(exc).__name__)
        return error(409, "integrity_conflict", "The request conflicts with a database integrity constraint.")

    @app.exception_handler(OperationalError)
    async def operational_error(_, exc):
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            response = error(503, "database_busy", "The ledger is busy. Retry using the same reference ID.")
            response.headers["Retry-After"] = "1"
            return response
        logger.exception("Database operation failed")
        return error(500, "database_error", "The database operation failed. No partial ledger operation was committed.")

    @app.exception_handler(Exception)
    async def unexpected_error(_, exc):
        logger.exception("Unexpected request failure")
        return error(500, "internal_error", "An unexpected error occurred. Refresh the account before retrying with the same reference ID.")

    @app.get("/health", tags=["System"])
    def health():
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return {"status": "ok"}

    @app.post("/api/accounts", status_code=201, response_model=schemas.AccountOut, tags=["Accounts"])
    def create_account(body: schemas.CreateAccount):
        return services.create_account(engine, body)

    @app.get("/api/accounts", response_model=list[schemas.AccountOut], tags=["Accounts"])
    def list_accounts():
        with Session(engine) as session:
            return [services.account_out(a) for a in session.scalars(select(Account).order_by(Account.created_at.desc(), Account.id))]

    @app.get("/api/accounts/{account_id}/balance", response_model=schemas.BalanceOut, tags=["Accounts"])
    def balance(account_id: UUID):
        with Session(engine) as session:
            account = services.require_account(session, account_id)
            return {"account_id": account.id, "balance": services.money(account.balance_cents)}

    @app.post("/api/accounts/{account_id}/transactions", status_code=201, response_model=schemas.TransactionOut, tags=["Transactions"])
    def create_transaction(account_id: UUID, body: schemas.CreateTransaction):
        return services.post_transaction(engine, account_id, body)

    @app.get("/api/accounts/{account_id}/transactions", response_model=schemas.HistoryOut, tags=["Transactions"])
    def history(account_id: UUID, type: Literal["credit", "debit"] | None = None,
                page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
                limit: Annotated[int, Query(ge=1, le=100)] = 10):
        return services.history(engine, account_id, type, page, limit)

    @app.post("/api/transfers", status_code=201, response_model=schemas.TransferOut, tags=["Transfers"])
    def transfer(body: schemas.CreateTransfer):
        return services.transfer(engine, body)

    return app


app = create_app()
