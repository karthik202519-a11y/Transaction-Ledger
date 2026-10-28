# Transaction Ledger

A complete local assessment application: Python FastAPI API, a persistent SQLite database, and a React + TypeScript interface. Create accounts, post credits and debits, inspect balances and paginated history, and transfer money between accounts.

## Run locally (Windows PowerShell)

Prerequisites: Python 3.12 or newer and Node.js 22 or newer. Verified versions are recorded in `docs/VALIDATION.md`. No database server, cloud account, or secret is required.

One-time setup:

```powershell
cd D:\UseCase
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
cd frontend
npm.cmd ci
```

Start the backend in one terminal:

```powershell
cd D:\UseCase
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```powershell
cd D:\UseCase\frontend
npm.cmd run dev
```

Alternatively, run `Start-Backend.ps1` and `Start-Frontend.ps1` in separate PowerShell terminals. Press Ctrl+C in each terminal to stop its server.

- Application: http://127.0.0.1:5173
- API Swagger documentation: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- API schema: http://127.0.0.1:8000/openapi.json
- Health: http://127.0.0.1:8000/health

Ports 8000 and 5173 are the user-requested ports. Vite proxies API requests to the backend. To use a different API port, set `LEDGER_API_TARGET` in the frontend terminal and use the same port in the Uvicorn command.

The database is created automatically at `backend/data/ledger.db`; startup never resets existing data. The delivered app starts empty. Browser tests use their own temporary database and never populate the application database.

## Use the application

1. Select **Create account** in the page header. Enter the account holder name in the dedicated view and submit. The app returns to the ledger with the new account selected at 0.00. Use **Back to ledger** to cancel.
2. Select **Credit**, enter a positive amount and unique reference, and record the entry.
3. Select **Debit** to withdraw funds. Overdraws are rejected.
4. Filter transaction history by type or move between pages.
5. Create another account, select the source account, and use **Transfer**. Both ledger entries and balances update together.

Amounts display in generic account units; no particular currency was specified. Entries are permanent. A repeated reference is rejected, including retries with a changed amount. After an uncertain network response, refresh first and retry using the same reference, never a newly generated one.

## Verify

Backend API, constraints, rollback, persistence, and concurrency tests:

```powershell
cd D:\UseCase\backend
..\.venv\Scripts\python.exe -m pytest -q --junitxml=../docs/backend-tests.xml
```

Frontend type check and production build:

```powershell
cd D:\UseCase\frontend
npm.cmd run build
```

Browser workflows on desktop and mobile Chromium:

```powershell
cd D:\UseCase\frontend
npx.cmd playwright install --no-shell chromium
npm.cmd run test:e2e
```

Browser tests start isolated servers on 8012 and 5175, stop them on completion, and create a temporary SQLite database in the OS temporary directory. Keep those ports free. Test screenshots are under `frontend/test-results/screenshots/`; HTML results are under `frontend/playwright-report/`. For an environment with an installed Microsoft Edge browser, set `$env:PLAYWRIGHT_CHANNEL='msedge'` before the browser tests to avoid downloading Chromium.

## Architecture

```text
React interface → Vite development proxy → FastAPI routes
                                           ↓ validation
                                      ledger services
                                           ↓ explicit transaction
                                     SQLAlchemy → SQLite
```

- `backend/app/schemas.py`: strict request fields, decimal validation, response contracts.
- `backend/app/models.py`: account and transaction tables, constraints, history index.
- `backend/app/database.py`: connection pragmas and explicit BEGIN/BEGIN IMMEDIATE.
- `backend/app/services.py`: balance rules, duplicate checks, atomic postings and transfers.
- `backend/app/main.py`: endpoints, consistent errors, startup, documentation.
- `backend/tests/`: requirement, failure-injection and concurrent-request verification.
- `frontend/src/`: UI, exact money formatting, API client and responsive styling.
- `frontend/tests/`: end-to-end browser workflows.
- `docs/API.md`: endpoint examples and error contract.
- `docs/assumptions.md`: limits and choices not specified by the assessment.
- `docs/VALIDATION.md`: actual verification results and scope.
- `docs/ASSESSMENT_REVERIFICATION.md`: 2026-10-28 PDF clause-by-clause checks, precision bug fix, and expanded test results.

## Integrity design

Money is validated as a decimal and stored as integer cents. Responses serialize amounts as fixed two-decimal strings, preserving precision through JavaScript. Constraints enforce positive transaction amounts, nonnegative balances, valid transaction types, foreign keys, and unique `(account_id, reference_id)` pairs.

Every write obtains SQLite's `BEGIN IMMEDIATE` lock before checking balances/references. All balance changes and ledger inserts share one transaction. Exceptions roll everything back. Reads use a transaction snapshot for consistent history counts/pages. WAL permits readers while a writer is active; SQLite still supports a single writer at a time. The busy timeout is 10 seconds, followed by HTTP 503 when contention remains. The tests use real file databases and separate connections.

A transfer inserts a debit and credit with a shared transfer ID, timestamp, amount and reference. Its reference must be unused on both accounts. Two-account updates and both inserts commit together. No API exposes transaction update/delete, account deletion, or direct balance editing.

This is a local assessment application with no login or authorization. It is not a deployment-ready banking service. Authentication, audit access controls, schema migration management, and operational backup policies are outside the assignment. Schema initialization creates missing tables; it does not migrate an existing incompatible schema.

## Assessment coverage

| Requirement | Implementation |
|---|---|
| Account creation, unique ID, zero balance, timestamp | POST /api/accounts |
| Credit/debit and sufficient funds | POST /api/accounts/{id}/transactions |
| Account-scoped duplicate prevention | Service checks + database unique constraint |
| Current balance | GET /api/accounts/{id}/balance |
| Filtered, paginated, latest-first history | GET /api/accounts/{id}/transactions |
| Immutable transaction API | Read/create endpoints only |
| Atomicity and consistent balances | Explicit SQLite transaction + rollback tests |
| Input validation and meaningful errors | Pydantic + common error envelope |
| Bonus transfer | POST /api/transfers |
| Local execution and documentation | This README, Swagger, API.md, assumptions.md |
| Additional React UI | Account, ledger and transfer workflows |
