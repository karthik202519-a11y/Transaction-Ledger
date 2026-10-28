# Validation report

Reverified locally on 2026-10-28. This report covers the completed assessment application in `D:\UseCase`. See [the complete PDF requirement matrix](ASSESSMENT_REVERIFICATION.md) for the second-pass cases, reproduced decimal-validation defect, correction, and final evidence. Current ports: UI 5173, API 8000.

## Verified environment

- Windows, PowerShell
- Python 3.14.3, isolated `.venv`
- Node.js 24.14.0, npm 11.9.0
- FastAPI 0.162.0, SQLAlchemy 2.1.6, Pydantic 2.14.1
- React 19, TypeScript 5.7, Vite 6 (exact npm resolutions in package-lock.json)
- Playwright Chromium 156, desktop 1440 × 1000 and Pixel 7 mobile emulation

## Results

| Check | Result | Evidence |
|---|---|---|
| Backend integration tests | **131 passed** | `backend-tests.xml` |
| Desktop/mobile browser workflows | **8 passed** | `browser-tests.xml`, `frontend/playwright-report/`; includes dedicated account-creation view |
| TypeScript check and production bundle | **Passed** | `npm run build`, `frontend/dist/` |
| Automated WCAG 2 A/AA and 2.1 AA checks | **0 violations on tested ledger views** | Assertions in `frontend/tests/ledger.spec.ts` |
| Document horizontal overflow | **None at tested desktop/mobile widths** | Browser test assertions |
| Browser JavaScript errors | **None in full ledger workflows** | Browser test assertions |
| npm dependency audit | **0 vulnerabilities reported at installation** | npm install output |
| Independent UI finish review | **Pass; no material fixes** | Read-only review of code and desktop/mobile screenshots |
| Live application/API | **Healthy** | UI, proxied API and Swagger returned 200; API health returned `ok`; verification did not write to the user's application database |

## Backend coverage

- Unique account IDs, required/trimmed names, zero starting balances, UTC timestamps, unknown-field rejection.
- Valid credits/debits and exact 0.10 + 0.20 arithmetic; full-balance debit to zero.
- Insufficient funds with unchanged balances and entry counts.
- Duplicate references, trimmed references, reuse across different accounts, unchanged balances on rejected duplicates.
- Invalid/zero/negative/over-precision amounts, NaN/infinity, booleans, nulls, wrong types, missing fields, invalid transaction types, oversized strings.
- Valid but unknown UUIDs, malformed UUIDs, malformed JSON, consistent error envelopes.
- Filtered history, pagination counts/limits, empty and beyond-last pages, latest-first ordering, deterministic timestamp ties.
- No transaction-edit/delete API; unsupported methods leave entries unchanged.
- Transfer linkage, correct balances, duplicate transfers, self-transfer/missing-account/insufficient-funds/reference conflicts.
- Maximum amount and balance bounds; destination overflow rolls back the source debit.
- Injected database failures on balance update, ledger insertion, and the transfer's second entry: no partial changes persisted.
- Database-level nonnegative/integer balances, foreign keys, account-scoped uniqueness.
- Ten concurrent 30-unit debits against 100: exactly three succeeded, seven rejected, final balance 10.
- Ten concurrent requests using the same reference: exactly one succeeded, nine rejected, one entry, balance 10.
- Eight concurrent 30-unit transfers against 100: exactly three succeeded, five rejected, source 10/destination 90.
- Data persisted after destroying and recreating the application against the same file database.
- Health and OpenAPI/Swagger routes.

## Browser coverage

Latest UI update (2026-10-28): Create account moved from the sidebar to a page-header button opening a dedicated view. Two additional desktop/mobile cases verify focus, blank-name rejection, cancel/back navigation, simulated creation error with preserved input, successful retry, zero starting balance, automatic selection, and accessibility/overflow. The full eight-scenario browser suite and production build passed. Earlier assessment re-verification totals of six browser scenarios are historical.

Each of three scenarios ran on desktop and mobile:

1. Create accounts, empty history, credit, duplicate error, insufficient funds, invalid precision, debit, filter, transfer, verify both balances, reload and check persistence.
2. Create more than one page of history, move forward/back, change page size, simulate failed history fetch, retry successfully, accessibility scan, viewport overflow check, screenshot capture.
3. Simulate failed account loading and recover with Refresh; hold a transaction request open and verify repeated submit/account creation are disabled; release it and verify one entry.

Tests use a dedicated temporary SQLite database and servers on ports 8012/5175. They do not write test records into the delivered application database. Screenshots contain explicitly synthetic test accounts.

## Evidence and limits

- Screenshots are generated when browser tests run, under `frontend/test-results/screenshots/`; generated screenshots and HTML reports are excluded from the submission.
- UI review disposition: **Pass**. Contract coverage, desktop/mobile composition, labels, focus states, retry controls and pending-write controls were inspected. No material findings remain. The reviewer did not independently rerun automated tests.
- A dependency emits a Starlette/httpx deprecation warning during backend tests; tests still pass. This is recorded rather than suppressed.
- The initial separate headless-shell browser download failed certificate validation. Tests successfully used the downloaded full Chromium with its supported `chromium` channel; TLS verification was not disabled.
- Mobile testing is Chromium device emulation, not a physical phone. Firefox, Safari, screen-reader navigation, production hosting, and sustained load testing were not performed.
- Automated accessibility results apply to the tested states, not a certification of every possible state.
- Authentication is intentionally absent from the approved assessment scope. Local integrity/concurrency tests do not establish production banking readiness.
