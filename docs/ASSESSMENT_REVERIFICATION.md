# Assessment re-verification — 2026-10-28

Source: all five pages of `Full Stack Developer Assessment_1451.pdf`, reread directly from the supplied Downloads path. The matrix below follows the PDF's actual clauses (its numbering skips section 6).

Final execution results are recorded in `backend-tests.xml` and `browser-tests.xml`. All write tests run against disposable databases; the user's application database was not reset or populated by this verification.

## Final results

| Check | Final result |
|---|---|
| Backend | **131 passed, 0 failed** in 53.57 seconds (62 more cases than the original 69) |
| Desktop/mobile browser scenarios | **6 passed, 0 failed** in 44.3 seconds |
| TypeScript + production build | **Passed** |
| Automated accessibility assertions | **Zero violations** on tested desktop/mobile populated ledger views |
| Python dependency consistency | `pip check`: no broken requirements |
| Live UI, API health, proxied API and Swagger | All returned **HTTP 200** on 5173/8000 |
| Live regression probe | Long-decimal request returned **422 validation_error**, with no write |
| Old application ports | No listeners remained on 8011/5174 |

**Disposition: all explicit assessment requirements passed in the tested scope after correcting the decimal-validation defect.**

## Finding and correction

The expanded tests reproduced a precision-validation bug. The old validator multiplied a Decimal by 100 before checking for a fractional remainder. Decimal's finite arithmetic context could round an input such as `1.000000000000000000000000000001` to `1.00`, admitting an amount that should be rejected. Extremely small exponents could instead reach the database and return 409 rather than a validation error.

The validator now examines the original decimal coefficient and exponent without rounded arithmetic or expanding the exponent. Invalid values return **422** before any ledger operation. Legitimate trailing zeros, scientific notation representing exact cents, the minimum cent, and the maximum amount remain accepted. Eight regression cases cover ordinary credits and transfers; the shared validator also governs debits. The initial reproduction had eight failing cases from this defect; all pass after the correction. The submission includes the final successful reports.

## PDF requirement matrix

Test references below use:

- **L:** `backend/tests/test_ledger.py`
- **R:** `backend/tests/test_assessment_reverification.py`
- **UI:** `frontend/tests/ledger.spec.ts`

| ID | PDF page | Requirement / case checked | Expected behavior and verification | Result |
|---|---|---|---|---|
| A01 | 1 | Account contains ID, name, balance, creation time | Exact response fields, parseable UUID and server-time interval; R `test_pdf_examples_and_complete_response_contracts` | Pass |
| A02 | 1 | Account IDs are unique | Two accounts with the same name receive different IDs; L `test_create_account_defaults_and_unique_ids` | Pass |
| A03 | 1 | Name required | Missing, null, empty, whitespace, wrong type, and excessive length rejected; L `test_invalid_account_body` | Pass |
| A04 | 1 | Initial balance always zero | New accounts report 0.00; L defaults test and R response-contract test | Pass |
| A05 | 1 | Client cannot set initial balance | Client `balance` and `balance_cents` fields rejected; L invalid-account tests | Pass |
| A06 | 1 | System-generated creation timestamp | Timestamp falls between request start and response; client timestamp rejected; R response-contract and L invalid-account tests | Pass |
| T01 | 1 | Transaction contains all specified fields | ID, account ID, type, amount, description, reference, timestamp verified; R response-contract test | Pass |
| T02 | 1 | Unique transaction IDs | Distinct parseable UUIDs across successful entries; R response-contract test | Pass |
| T03 | 1 | Credit increases balance | PDF sequence 100 + 50 = 150 checked at the intermediate step; R response-contract test | Pass |
| T04 | 2 | Debit decreases balance | 100 − 30 = 70 is exercised by transfer; ordinary debit sequence and exact-zero debit also tested; L credit/debit and R response-contract tests | Pass |
| T05 | 2 | Insufficient debit rejected | 150 debit against 100 returns 409; balance stays 100 and entry count stays unchanged; L `test_debit_exact_balance_and_insufficient_funds` | Pass |
| T06 | 2 | Reference unique within account | Repeated trimmed reference rejected, including changed amount/type; L duplicate-reference test | Pass |
| T07 | 2 | Duplicate adds no transaction | Original entry count unchanged; L duplicate-reference and concurrent-duplicate tests | Pass |
| T08 | 2 | Duplicate leaves balance unchanged | Exactly one posting survives repeated concurrent reference; L concurrent-duplicate test | Pass |
| T09 | 2 | Meaningful duplicate response | HTTP 409 with `duplicate_transaction`; L duplicate-reference test | Pass |
| T10 | 2 | Same reference allowed on different accounts | Matching references posted successfully to two different accounts; L duplicate-reference test | Pass |
| B01 | 2 | Balance returns account ID and current balance | Exact response contract and updated values verified; R response-contract test | Pass |
| B02 | 2 | Missing account error | Unknown UUID returns 404 for balance/history/posting; malformed UUID returns 422; L `test_unknown_and_malformed_accounts` | Pass |
| H01 | 2 | Credit history filter | Only credits for the selected account returned; R `test_both_filters_account_isolation_and_metadata[credit]` | Pass |
| H02 | 2 | Debit history filter | Only debits for the selected account returned; R debit filter case | Pass |
| H03 | 2 | Omitted type returns both | Both credit and debit recovered across pages; R unfiltered case | Pass |
| H04 | 3 | Page/limit pagination | First/second page, changed page size, empty and beyond-last page; L pagination test and UI pagination workflow | Pass |
| H05 | 3 | Pagination metadata | Current page, page size, total records and total pages checked, including filtered counts; R filter/metadata cases | Pass |
| H06 | 3 | Latest-first by created_at | Deliberately out-of-insertion-order timestamps sort correctly; R timestamp-order test; L tie-breaker test | Pass |
| I01 | 3 | Transactions cannot be edited/deleted | PUT/PATCH/DELETE on collection and individual nested/top-level paths rejected; R immutable-field cases | Pass |
| I02 | 3 | Every immutable field remains unchanged | Whole original records compared after mutation attempts: type, amount, description, reference, account ID, timestamp; R immutable-field cases | Pass |
| I03 | 3 | Balance equals valid transactions | PDF sequence ends at 100; independent model checks all balances and complete records after each of 120 mixed requests; R response-contract and reconciliation tests | Pass |
| I04 | 3 | Failed/rejected requests do not affect balance | Full before/after snapshots for invalid bodies, transfers, precision, rollback and lock contention; L/R tests | Pass |
| I05 | 4 | Posting and balance update are atomic | Injected insertion and balance-update failures roll back both; L `test_injected_database_failure_rolls_back_everything` | Pass |
| V01 | 4 | Account must exist for posting | Missing account rejected without a ledger row; L unknown-account tests | Pass |
| V02 | 4 | Type must be credit/debit | Invalid/capitalized types rejected; L invalid-field tests | Pass |
| V03 | 4 | Amount greater than zero | Zero, negative, null, bool, nonnumeric, nonfinite, excessive precision and bounds rejected; L invalid-amount and R precision tests | Pass |
| V04 | 4 | Reference required | Missing, blank, null, wrong type and oversized reference rejected; L missing/invalid-field and R transfer-validation tests | Pass |
| V05 | 4 | Invalid account ID handled | Malformed UUID 422 and unknown UUID 404; L unknown-account tests | Pass |
| V06 | 4 | Invalid request body handled | Null, arrays, JSON strings, empty objects, malformed JSON tested on all three POST endpoints; R body-validation cases | Pass |
| E01 | 4 | Appropriate HTTP codes and meaningful errors | 201 success; 404 account missing; 409 duplicate/funds/integrity; 422 validation; 500 injected commit failure; 503 real lock timeout | Pass |
| E02 | 4 | Invalid pagination handled | Zero/negative/noninteger/nonnumeric page/limit, over-limit page/limit and invalid filter rejected; L pagination-validation cases | Pass |
| E03 | 4 | Consistent understandable error envelope | `error.code`, `error.message`, `error.details`; validation details; private database/exception text not exposed; L/R cases | Pass |
| X01 | 4–5 | Bonus transfer example | A=100, B=50, transfer=30 produces A=70, B=80; L transfer and R response-contract tests | Pass |
| X02 | 5 | Source has sufficient balance | Overdraw rejected with both snapshots unchanged; L transfer-rejection test | Pass |
| X03 | 5 | Both accounts exist | Unknown source and unknown destination rejected; L transfer-rejection test | Pass |
| X04 | 5 | Both sides update atomically | Linked debit/credit, correct balances, shared timestamp/transfer ID; L transfer-success test | Pass |
| X05 | 5 | Any transfer failure fully rolls back | Separate source update, destination update, debit insertion, credit insertion, and pre-commit failure injections; R five-stage rollback test | Pass |
| X06 | 5 | No partial transfer | Both balances and all original entries compared after each injected failure; same reference succeeds after fault removal | Pass |
| Q01 | 5 | Backend and database choice | FastAPI + persistent SQLite, permitted by PDF and requested by user; source/config inspection | Pass |
| Q02 | 5 | Clean maintainable structure | Separate route, request-schema, model, database and ledger-service modules; React API/UI/styles; manual inspection | Pass |
| Q03 | 5 | Database constraints | FK, unique account reference, integer/nonnegative balance, positive/bounded amount, valid type/reference/description checks tested directly; L/R DB tests | Pass |
| Q04 | 5 | Runnable locally using README | Uvicorn/Vite commands started successfully in current installed environment; live UI/proxy/docs/health verified on 5173/8000 | Pass |
| S01 | 5 | Source code submission | Backend/frontend source files present; backend tests and TypeScript production build execute them | Pass |
| S02 | 5 | README submission | README and launcher scripts exist; ports and commands updated to 8000/5173; R submission-file test + live startup | Pass |
| S03 | 5 | API documentation submission | Swagger serves; saved OpenAPI equals runtime schema; API examples supplied; R submission-contract test | Pass |
| S04 | 5 | Assumptions submission | `docs/assumptions.md` supplied: description optional, generic units, precision, references, limits, persistence and scope | Pass |

## Additional robustness and UI checks

- 16 simultaneous 0.01 credits: all succeed, final balance 0.16, 16 rows; no lost updates.
- 10 simultaneous 30-unit debits against 100: three accepted, seven rejected, final balance 10.
- 10 identical concurrent references: one accepted, nine rejected, one row.
- Eight simultaneous transfers against 100: three accepted, five rejected; total funds conserved.
- Twelve opposing transfers: all accepted, each account remains at 100; every ledger reconciles.
- Actual SQLite write-lock contention: controlled test timeout returns 503 and Retry-After; no mutation; same-reference retry succeeds after release. Production timeout remains 10 seconds.
- Source/destination balance limits, minimum cent, maximum amount, exact trailing-zero values, and persistence across application restart.
- Both `localhost:5173` and `127.0.0.1:5173` CORS preflights accepted.
- Six desktop/mobile browser scenarios cover full workflows, duplicate/insufficient-funds/precision errors, filters, pagination, fetch failure/retry, disabled pending writes, reload, layout overflow, and automated WCAG scans.

## Port change

Per explicit user instruction, the SPINA backend/reloader and frontend occupying ports 8000/5173 were stopped. This assessment app's previous 8011/5174 processes were also stopped. The assessment now runs at:

- UI: http://127.0.0.1:5173
- API docs: http://127.0.0.1:8000/docs

Startup script, Vite proxy/default port, API CORS origins, README and API examples reflect these ports. Automated browser tests keep their separate 8012/5175 ports.

## Limits of the evidence

Every explicit PDF requirement above has been reviewed and exercised where executable. This is not an exhaustive enumeration of all possible input values. Optional descriptions and the two-decimal money model are documented, approved assumptions; the PDF does not specify either policy. Tests are local, mobile is emulated Chromium, and no production hosting/load/security certification is claimed. A third-party Starlette/httpx deprecation warning remains; it is not a failed test. Fresh-machine dependency installation was not repeated; startup was verified using the existing pinned environment.
