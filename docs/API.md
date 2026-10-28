# API reference

Base URL: `http://127.0.0.1:8000`. Interactive documentation: `/docs`. Machine-readable schema: `/openapi.json` and the submitted `openapi.json` snapshot in this directory.

## Accounts

`POST /api/accounts` → 201

```json
{"name": "Alice"}
```

Response:

```json
{"id":"<generated-uuid>","name":"Alice","balance":"0.00","created_at":"<UTC ISO timestamp>"}
```

Only `name` is accepted. Sending `balance`, including zero, is rejected. `GET /api/accounts` returns an array of these objects, newest accounts first.

`GET /api/accounts/{account_id}/balance` → 200

```json
{"account_id":"<uuid>","balance":"100.00"}
```

## Transactions

`POST /api/accounts/{account_id}/transactions` → 201

```json
{"type":"credit","amount":"100.00","reference_id":"payment-001","description":"Opening credit"}
```

`type` is `credit` or `debit`. `description` may be omitted. The response includes `id`, `account_id`, `type`, `amount`, `description`, `reference_id`, `created_at`, and `transfer_id` (null for ordinary entries).

`GET /api/accounts/{account_id}/transactions?type=credit&page=1&limit=10` → 200

Omit `type` to retrieve both credits and debits. Results sort newest first.

```json
{"items":[],"current_page":1,"page_size":10,"total_records":0,"total_pages":0}
```

## Transfers

`POST /api/transfers` → 201

```json
{"source_account_id":"<source-uuid>","destination_account_id":"<destination-uuid>","amount":"30.00","reference_id":"transfer-001","description":"Reserve allocation"}
```

Response includes `transfer_id`, `source_balance`, `destination_balance`, and full `debit`/`credit` transaction objects. Both accounts must exist and differ. The reference must be unused on both. Source funds must be sufficient and destination balance must remain within the documented bound. The complete operation rolls back on any failure.

## Error contract

All errors use this envelope:

```json
{"error":{"code":"insufficient_balance","message":"The account does not have sufficient balance.","details":[]}}
```

Validation details have `field` and `message`, for example `body.amount` and the applicable validation message. Raw SQL and tracebacks are not returned.

| Status | Meaning |
|---|---|
| 404 | Validly formatted account ID does not exist, or route does not exist |
| 405 | Method is not exposed on this route |
| 409 | Duplicate reference, insufficient balance, balance limit, or database constraint conflict |
| 422 | Malformed UUID/JSON, missing/unknown fields, invalid type/amount, pagination, or same-account transfer |
| 500 | Unexpected failure; refresh before retrying with the same reference |
| 503 | Database is busy after its lock timeout; `Retry-After: 1` |

`GET /health` verifies database connectivity and returns `{"status":"ok"}`.

## PowerShell example

```powershell
$base = 'http://127.0.0.1:8000'
$account = Invoke-RestMethod -Method Post -Uri "$base/api/accounts" -ContentType 'application/json' -Body '{"name":"Alice"}'
$accountId = $account.id
Invoke-RestMethod -Method Post -Uri "$base/api/accounts/$accountId/transactions" -ContentType 'application/json' -Body '{"type":"credit","amount":"100.00","reference_id":"opening-001"}'
Invoke-RestMethod -Uri "$base/api/accounts/$accountId/balance"
Invoke-RestMethod -Uri "$base/api/accounts/$accountId/transactions?page=1&limit=10"
```
