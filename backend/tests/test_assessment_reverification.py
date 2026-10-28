"""Second-pass PDF traceability, boundary, failure and reconciliation tests."""
import random
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from test_ledger import account, balance, history, post, run_concurrently, transfer


def snapshot(client, aid):
    return balance(client, aid), history(client, aid, '?limit=100')


def test_pdf_examples_and_complete_response_contracts(client):
    before = datetime.now(timezone.utc)
    a, b = account(client), account(client, 'Bob')
    accounts = client.get('/api/accounts').json()
    for row in accounts:
        assert set(row) == {'id', 'name', 'balance', 'created_at'}
        assert UUID(row['id']).version == 4
        assert before <= datetime.fromisoformat(row['created_at']) <= datetime.now(timezone.utc)
    entries = []
    for amount, kind, expected in [('100', 'credit', '100.00'), ('50', 'credit', '150.00'),
                                   ('30', 'debit', '120.00'), ('20', 'debit', '100.00')]:
        response = post(client, a, amount, kind)
        assert response.status_code == 201
        row = response.json()
        assert set(row) == {'id', 'account_id', 'type', 'amount', 'description', 'reference_id', 'created_at', 'transfer_id'}
        assert UUID(row['id']).version == 4
        assert row['account_id'] == a and row['type'] == kind
        assert row['description'] == '' and row['transfer_id'] is None
        assert before <= datetime.fromisoformat(row['created_at']) <= datetime.now(timezone.utc)
        assert balance(client, a) == expected
        entries.append(row['id'])
    assert len(set(entries)) == 4
    assert client.get(f'/api/accounts/{a}/balance').json() == {'account_id': a, 'balance': '100.00'}
    post(client, b, '50')
    assert transfer(client, a, b).status_code == 201
    assert balance(client, a) == '70.00' and balance(client, b) == '80.00'


@pytest.mark.parametrize('kind', ['credit', 'debit', None])
def test_both_filters_account_isolation_and_metadata(client, kind):
    a, b = account(client), account(client, 'Bob')
    post(client, a, '10', reference='a-credit')
    post(client, a, '1', 'debit', reference='a-debit')
    post(client, b, '100', reference='other-account')
    query = '?page=1&limit=1' + (f'&type={kind}' if kind else '')
    result = history(client, a, query)
    assert set(result) == {'items', 'current_page', 'page_size', 'total_records', 'total_pages'}
    assert result['total_records'] == (1 if kind else 2)
    assert result['total_pages'] == (1 if kind else 2)
    assert result['current_page'] == result['page_size'] == 1
    assert result['items'][0]['account_id'] == a
    if kind:
        assert result['items'][0]['type'] == kind
    else:
        second = history(client, a, '?page=2&limit=1')
        assert {result['items'][0]['type'], second['items'][0]['type']} == {'credit', 'debit'}


def test_sorting_uses_timestamp_before_insertion_sequence(client, app):
    aid = account(client)
    dates = ['2026-01-03', '2026-01-01', '2026-01-02']
    for i, day in enumerate(dates):
        result = post(client, aid, reference=f'r{i}')
        with app.state.engine.begin() as conn:
            conn.exec_driver_sql('UPDATE transactions SET created_at = ? WHERE id = ?',
                                 (day + 'T00:00:00.000000+00:00', result.json()['id']))
    assert [t['reference_id'] for t in history(client, aid)['items']] == ['r0', 'r2', 'r1']


@pytest.mark.parametrize('method', ['PATCH', 'PUT', 'DELETE'])
def test_every_immutable_field_stays_identical(client, method):
    a, b = account(client), account(client, 'Bob')
    original = post(client, a, '10', reference='permanent', description='Original description').json()
    before = snapshot(client, a)
    changes = {'type': 'debit', 'amount': '1', 'description': 'Changed', 'reference_id': 'changed',
               'account_id': b, 'created_at': '2000-01-01T00:00:00Z'}
    for path in [f'/api/accounts/{a}/transactions/{original["id"]}', f'/api/transactions/{original["id"]}',
                 f'/api/accounts/{a}/transactions']:
        response = client.request(method, path, json=changes)
        assert response.status_code in (404, 405)
    assert snapshot(client, a) == before
    assert history(client, b)['items'] == []


@pytest.mark.parametrize('amount', ['1.000000000000000000000000000001',
    '9999999999.980000000000000000000000001', '0.0100000000000000000000000000001', '1e-999999999'])
@pytest.mark.parametrize('operation', ['credit', 'transfer'])
def test_precision_beyond_decimal_context_is_rejected(client, amount, operation):
    a, b = account(client), account(client, 'Bob')
    post(client, a, '100')
    before = snapshot(client, a), snapshot(client, b)
    response = post(client, a, amount) if operation == 'credit' else transfer(client, a, b, amount)
    assert response.status_code == 422, response.text
    assert (snapshot(client, a), snapshot(client, b)) == before


@pytest.mark.parametrize('amount,expected', [('0.01', '0.01'), ('1.230000000000000000000000000000', '1.23'),
    ('1e2', '100.00'), (0.1, '0.10'), ('9999999999.99', '9999999999.99')])
def test_valid_money_boundaries_remain_exact(client, amount, expected):
    aid = account(client)
    result = post(client, aid, amount)
    assert result.status_code == 201, result.text
    assert result.json()['amount'] == balance(client, aid) == expected


@pytest.mark.parametrize('endpoint', ['accounts', 'transaction', 'transfer'])
@pytest.mark.parametrize('body', ['null', '[]', '"text"', '{}', '{broken'])
def test_wrong_request_bodies_have_consistent_errors(client, endpoint, body):
    aid = account(client)
    path = {'accounts': '/api/accounts', 'transaction': f'/api/accounts/{aid}/transactions', 'transfer': '/api/transfers'}[endpoint]
    result = client.post(path, content=body, headers={'Content-Type': 'application/json'})
    assert result.status_code == 422
    assert set(result.json()) == {'error'}
    assert set(result.json()['error']) == {'code', 'message', 'details'}
    assert result.json()['error']['details']
    assert balance(client, aid) == '0.00'


@pytest.mark.parametrize('field,value', [('source_account_id', None), ('destination_account_id', 'invalid'),
    ('reference_id', ''), ('reference_id', 123), ('amount', True), ('description', 'x' * 501), ('extra', 'unexpected')])
def test_transfer_validation_cannot_mutate_either_account(client, field, value):
    a, b = account(client), account(client, 'Bob')
    post(client, a, '100')
    body = {'source_account_id': a, 'destination_account_id': b, 'amount': '10', 'reference_id': 'r'}
    body[field] = value
    before = snapshot(client, a), snapshot(client, b)
    assert client.post('/api/transfers', json=body).status_code == 422
    assert (snapshot(client, a), snapshot(client, b)) == before


@pytest.mark.parametrize('stage', ['source_update', 'destination_update', 'debit_insert', 'credit_insert', 'commit'])
def test_transfer_failure_at_every_write_stage_and_retry(client, app, stage):
    a, b = account(client), account(client, 'Bob')
    post(client, a, '100'); post(client, b, '50')
    before = snapshot(client, a), snapshot(client, b)
    def fail_commit(_connection):
        raise RuntimeError('injected commit failure: private detail')
    if stage == 'commit':
        event.listen(app.state.engine, 'commit', fail_commit)
    else:
        if stage.endswith('update'):
            target = a if stage == 'source_update' else b
            trigger = f"BEFORE UPDATE ON accounts WHEN NEW.id = '{target}'"
        else:
            kind = 'debit' if stage == 'debit_insert' else 'credit'
            trigger = f"BEFORE INSERT ON transactions WHEN NEW.type = '{kind}' AND NEW.transfer_id IS NOT NULL"
        with app.state.engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE TRIGGER injected_failure {trigger} BEGIN SELECT RAISE(ABORT, 'private detail'); END")
    try:
        result = transfer(client, a, b, reference='retry-same-reference')
        assert result.status_code == (500 if stage == 'commit' else 409)
        assert 'private detail' not in result.text
        assert (snapshot(client, a), snapshot(client, b)) == before
    finally:
        if stage == 'commit':
            event.remove(app.state.engine, 'commit', fail_commit)
        else:
            with app.state.engine.begin() as conn:
                conn.exec_driver_sql('DROP TRIGGER injected_failure')
    assert transfer(client, a, b, reference='retry-same-reference').status_code == 201
    assert balance(client, a) == '70.00' and balance(client, b) == '80.00'


def test_database_busy_rolls_back_and_same_reference_can_retry(client, app):
    aid = account(client)
    before = snapshot(client, aid)
    # Use a short timeout only on test connections; exercise an actual SQLite lock.
    def short_timeout(connection, _):
        connection.execute('PRAGMA busy_timeout=50')
    app.state.engine.dispose()
    event.listen(app.state.engine, 'connect', short_timeout)
    with app.state.engine.connect().execution_options(sqlite_begin_mode='IMMEDIATE') as lock:
        with lock.begin():
            result = post(client, aid, reference='busy-retry')
            assert result.status_code == 503
            assert result.json()['error']['code'] == 'database_busy'
            assert result.headers['Retry-After'] == '1'
    assert snapshot(client, aid) == before
    assert post(client, aid, reference='busy-retry').status_code == 201
    assert balance(client, aid) == '10.00'


@pytest.mark.parametrize('change', ["type='other'", 'amount_cents=0', 'amount_cents=-1',
    'amount_cents=0.5', 'amount_cents=1000000000000', "reference_id=''", "description='" + 'x' * 501 + "'"])
def test_transaction_database_checks(client, app, change):
    aid = account(client)
    original = post(client, aid).json()
    with pytest.raises(IntegrityError), app.state.engine.begin() as conn:
        conn.exec_driver_sql(f'UPDATE transactions SET {change} WHERE id = ?', (original['id'],))
    assert history(client, aid)['items'][0] == original


def test_concurrent_credits_do_not_lose_updates(client):
    aid = account(client)
    results = run_concurrently(16, lambda i: post(client, aid, '0.01', reference=f'cent-{i}'))
    assert all(r.status_code == 201 for r in results)
    assert balance(client, aid) == '0.16'
    assert history(client, aid)['total_records'] == 16


def test_opposing_transfers_preserve_ledger_and_original_entries(client):
    a, b = account(client), account(client, 'Bob')
    post(client, a, '100'); post(client, b, '100')
    results = run_concurrently(12, lambda i: transfer(client, a if i % 2 else b, b if i % 2 else a, '1', f'opposing-{i}'))
    assert all(r.status_code == 201 for r in results)
    assert balance(client, a) == balance(client, b) == '100.00'
    for aid in [a, b]:
        rows = history(client, aid, '?limit=100')['items']
        assert len(rows) == 13
        assert sum(Decimal(t['amount']) * (1 if t['type'] == 'credit' else -1) for t in rows) == Decimal('100')


def test_seeded_mixed_operations_reconcile_after_every_request(client):
    rng = random.Random(1451)
    ids = [account(client, f'Model account {i}') for i in range(4)]
    expected_balances = {aid: 0 for aid in ids}
    expected_entries = {aid: {} for aid in ids}
    for step in range(120):
        source, destination = rng.sample(ids, 2)
        kind = rng.choice(['credit', 'debit', 'transfer'])
        cents = rng.randint(1, 10000)
        amount = f'{cents // 100}.{cents % 100:02d}'
        reference = f'model-{rng.randint(0, 25)}'
        duplicate = any(t['reference_id'] == reference for t in expected_entries[source].values())
        if kind == 'transfer':
            duplicate |= any(t['reference_id'] == reference for t in expected_entries[destination].values())
        valid = not duplicate and (kind == 'credit' or expected_balances[source] >= cents)
        result = transfer(client, source, destination, amount, reference) if kind == 'transfer' else post(client, source, amount, kind, reference)
        assert result.status_code == (201 if valid else 409), (step, result.text)
        if valid:
            expected_balances[source] += cents if kind == 'credit' else -cents
            rows = [result.json()] if kind != 'transfer' else [result.json()['debit'], result.json()['credit']]
            if kind == 'transfer':
                expected_balances[destination] += cents
            for row in rows:
                expected_entries[row['account_id']][row['id']] = row
        for aid in ids:
            assert Decimal(balance(client, aid)) * 100 == expected_balances[aid], (step, aid)
            current = history(client, aid, '?limit=100')
            assert current['total_records'] == len(expected_entries[aid])
            assert {t['id']: t for t in current['items']} == expected_entries[aid]


def test_submission_files_and_openapi_match_current_application(client):
    import json
    root = Path(__file__).resolve().parents[2]
    for filename in ['README.md', 'docs/API.md', 'docs/assumptions.md', 'backend/requirements.lock.txt', 'frontend/package-lock.json',
                     'Start-Backend.ps1', 'Start-Frontend.ps1']:
        assert (root / filename).is_file() and (root / filename).stat().st_size > 0
    assert json.loads((root / 'docs/openapi.json').read_text(encoding='utf-8')) == client.get('/openapi.json').json()


@pytest.mark.parametrize('origin', ['http://localhost:5173', 'http://127.0.0.1:5173'])
def test_requested_frontend_port_cors(client, origin):
    result = client.options('/api/accounts', headers={
        'Origin': origin, 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type'})
    assert result.status_code == 200
    assert result.headers['access-control-allow-origin'] == origin
