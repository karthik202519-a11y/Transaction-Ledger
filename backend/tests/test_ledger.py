from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import Account, Transaction


def account(client, name="Alice"):
    result = client.post('/api/accounts', json={"name": name})
    assert result.status_code == 201, result.text
    return result.json()['id']


def post(client, account_id, amount="10.00", kind="credit", reference=None, **extra):
    return client.post(f'/api/accounts/{account_id}/transactions', json={
        "amount": amount, "type": kind, "reference_id": reference or str(uuid4()), **extra})


def balance(client, account_id):
    response = client.get(f'/api/accounts/{account_id}/balance')
    assert response.status_code == 200
    return response.json()['balance']


def history(client, account_id, query=""):
    response = client.get(f'/api/accounts/{account_id}/transactions{query}')
    assert response.status_code == 200
    return response.json()


def transfer(client, source, destination, amount="30.00", reference=None):
    return client.post('/api/transfers', json={"source_account_id": source,
        "destination_account_id": destination, "amount": amount,
        "reference_id": reference or str(uuid4()), "description": "Transfer"})


def test_create_account_defaults_and_unique_ids(client):
    ids = [account(client, "  Alice  ") for _ in range(2)]
    assert ids[0] != ids[1]
    items = client.get('/api/accounts').json()
    assert len(items) == 2
    for item in items:
        assert item['name'] == 'Alice'
        assert item['balance'] == '0.00'
        assert item['created_at'].endswith('+00:00')


@pytest.mark.parametrize('body', [{}, {"name": ""}, {"name": "   "}, {"name": None},
    {"name": 123}, {"name": "a" * 121}, {"name": "Alice", "balance": 0},
    {"name": "Alice", "balance_cents": 100}, {"name": "Alice", "id": str(uuid4())},
    {"name": "Alice", "created_at": "yesterday"}])
def test_invalid_account_body(client, body):
    response = client.post('/api/accounts', json=body)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'
    assert client.get('/api/accounts').json() == []


def test_credit_debit_exact_money_and_balance_consistency(client):
    aid = account(client)
    for amount, kind in [('100', 'credit'), ('50', 'credit'), ('30', 'debit'), ('20', 'debit'), ('0.10', 'credit'), ('0.20', 'credit')]:
        response = post(client, aid, amount, kind, description="Test payment")
        assert response.status_code == 201
        assert response.json()['created_at'].endswith('+00:00')
        assert response.json()['description'] == 'Test payment'
    assert balance(client, aid) == '100.30'
    entries = history(client, aid)['items']
    assert sum(Decimal(t['amount']) * (1 if t['type'] == 'credit' else -1) for t in entries) == Decimal('100.30')


def test_debit_exact_balance_and_insufficient_funds(client):
    aid = account(client)
    post(client, aid, '100')
    result = post(client, aid, '150', 'debit')
    assert result.status_code == 409
    assert result.json()['error']['code'] == 'insufficient_balance'
    assert balance(client, aid) == '100.00'
    assert history(client, aid)['total_records'] == 1
    assert post(client, aid, '100', 'debit').status_code == 201
    assert balance(client, aid) == '0.00'


def test_duplicate_reference_is_scoped_to_account_and_trimmed(client):
    a, b = account(client), account(client, 'Bob')
    assert post(client, a, reference=' ref-1 ').status_code == 201
    for kind in ['credit', 'debit']:
        response = post(client, a, '999', kind, reference='ref-1')
        assert response.status_code == 409
        assert response.json()['error']['code'] == 'duplicate_transaction'
    assert balance(client, a) == '10.00'
    assert history(client, a)['total_records'] == 1
    assert post(client, b, reference='ref-1').status_code == 201


@pytest.mark.parametrize('amount', [0, -1, '0.00', '-0.01', '0.001', '1.234', 'not-money',
    'NaN', 'Infinity', '-Infinity', True, False, None, '', '10000000000.00', [], {}])
def test_invalid_amounts_leave_no_writes(client, amount):
    aid = account(client)
    assert post(client, aid, amount).status_code == 422
    assert balance(client, aid) == '0.00'
    assert history(client, aid)['total_records'] == 0


@pytest.mark.parametrize('changes', [{"type": "other"}, {"type": "CREDIT"}, {"reference_id": " "},
    {"reference_id": "x" * 121}, {"reference_id": None}, {"description": "x" * 501},
    {"description": None}, {"account_id": str(uuid4())}, {"id": str(uuid4())}, {"created_at": "today"}])
def test_invalid_transaction_fields(client, changes):
    aid = account(client)
    payload = {"type": "credit", "amount": "10", "reference_id": "r"} | changes
    result = client.post(f'/api/accounts/{aid}/transactions', json=payload)
    assert result.status_code == 422
    assert balance(client, aid) == '0.00'


@pytest.mark.parametrize('missing', ['type', 'amount', 'reference_id'])
def test_missing_transaction_fields(client, missing):
    aid = account(client)
    payload = {"type": "credit", "amount": "10", "reference_id": "r"}
    del payload[missing]
    assert client.post(f'/api/accounts/{aid}/transactions', json=payload).status_code == 422


def test_unknown_and_malformed_accounts(client):
    for aid, expected in [(str(uuid4()), 404), ('not-a-uuid', 422)]:
        for suffix in ['balance', 'transactions']:
            assert client.get(f'/api/accounts/{aid}/{suffix}').status_code == expected
        assert post(client, aid).status_code == expected


def test_history_pagination_filtering_and_stable_order(client, app):
    aid = account(client)
    # Freeze timestamps to exercise the sequence tie-breaker, not clock precision.
    def fixed_timestamp(_mapper, _connection, target):
        target.created_at = '2026-01-01T00:00:00.000000+00:00'
    event.listen(Transaction, 'before_insert', fixed_timestamp)
    try:
        for i in range(15):
            assert post(client, aid, '1', 'credit' if i % 2 == 0 else 'debit', f'ref-{i}').status_code == 201
    finally:
        event.remove(Transaction, 'before_insert', fixed_timestamp)
    first, second = history(client, aid, '?page=1&limit=10'), history(client, aid, '?page=2&limit=10')
    assert first['total_pages'] == 2 and first['total_records'] == 15
    assert first['page_size'] == 10 and first['current_page'] == 1
    assert [t['reference_id'] for t in first['items'] + second['items']] == [f'ref-{i}' for i in reversed(range(15))]
    filtered = history(client, aid, '?type=debit&limit=3')
    assert filtered['total_records'] == 7 and filtered['total_pages'] == 3
    assert all(t['type'] == 'debit' for t in filtered['items'])
    assert history(client, aid, '?page=99')['items'] == []
    empty = history(client, account(client, 'Empty'))
    assert empty['total_pages'] == 0 and empty['items'] == []


@pytest.mark.parametrize('query', ['?page=0', '?page=-1', '?page=abc', '?page=1.5', '?limit=0', '?limit=-1', '?limit=101', '?limit=abc', '?type=other', '?page=1000001'])
def test_invalid_pagination(client, query):
    aid = account(client)
    assert client.get(f'/api/accounts/{aid}/transactions{query}').status_code == 422


def test_immutability_and_error_envelope(client):
    aid = account(client)
    tid = post(client, aid).json()['id']
    for method in ['patch', 'put', 'delete']:
        for path in [f'/api/accounts/{aid}/transactions', f'/api/transactions/{tid}', f'/api/accounts/{aid}']:
            response = getattr(client, method)(path)
            assert response.status_code in [404, 405]
            assert set(response.json()['error']) == {'code', 'message', 'details'}
    assert balance(client, aid) == '10.00'
    assert history(client, aid)['items'][0]['id'] == tid


def test_malformed_json_and_documentation(client):
    response = client.post('/api/accounts', content='{broken', headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert response.json()['error']['details']
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/docs').status_code == 200
    assert '/api/transfers' in client.get('/openapi.json').json()['paths']


def test_transfer_success_and_duplicate(client):
    a, b = account(client), account(client, 'Bob')
    post(client, a, '100'); post(client, b, '50')
    response = transfer(client, a, b, reference='transfer-1')
    assert response.status_code == 201, response.text
    body = response.json()
    assert balance(client, a) == '70.00' and balance(client, b) == '80.00'
    assert body['debit']['transfer_id'] == body['credit']['transfer_id'] == body['transfer_id']
    assert body['debit']['type'] == 'debit' and body['credit']['type'] == 'credit'
    assert body['debit']['created_at'] == body['credit']['created_at']
    assert transfer(client, a, b, reference='transfer-1').status_code == 409
    assert balance(client, a) == '70.00' and balance(client, b) == '80.00'


def test_transfer_rejections_are_atomic(client):
    a, b = account(client), account(client, 'Bob')
    post(client, a, '100'); post(client, b, '10', reference='used')
    assert transfer(client, a, b, '101').status_code == 409
    assert transfer(client, a, a).status_code == 422
    assert transfer(client, a, str(uuid4())).status_code == 404
    assert transfer(client, str(uuid4()), b).status_code == 404
    assert transfer(client, a, b, reference='used').status_code == 409
    assert transfer(client, a, b, '0.001').status_code == 422
    assert balance(client, a) == '100.00' and balance(client, b) == '10.00'
    assert history(client, a)['total_records'] == history(client, b)['total_records'] == 1


def test_balance_limit_and_transfer_overflow_roll_back(client):
    a, b = account(client), account(client, 'Bob')
    assert post(client, a, '9999999999.99').status_code == 201
    assert post(client, a, '0.01').status_code == 409
    post(client, b, '5')
    assert transfer(client, b, a, '1').status_code == 409
    assert balance(client, a) == '9999999999.99' and balance(client, b) == '5.00'
    assert history(client, b)['total_records'] == 1


@pytest.mark.parametrize('failure_point', ['entry', 'balance', 'second_transfer_entry'])
def test_injected_database_failure_rolls_back_everything(client, app, failure_point):
    a, b = account(client), account(client, 'Bob')
    post(client, a, '100')
    with app.state.engine.begin() as conn:
        if failure_point == 'balance':
            conn.exec_driver_sql("CREATE TRIGGER fail_test BEFORE UPDATE ON accounts BEGIN SELECT RAISE(ABORT, 'injected'); END")
        elif failure_point == 'entry':
            conn.exec_driver_sql("CREATE TRIGGER fail_test BEFORE INSERT ON transactions BEGIN SELECT RAISE(ABORT, 'injected'); END")
        else:
            conn.exec_driver_sql("CREATE TRIGGER fail_test BEFORE INSERT ON transactions WHEN NEW.type = 'credit' AND NEW.transfer_id IS NOT NULL BEGIN SELECT RAISE(ABORT, 'injected'); END")
    response = transfer(client, a, b) if failure_point == 'second_transfer_entry' else post(client, a, '1')
    assert response.status_code == 409
    assert balance(client, a) == '100.00' and balance(client, b) == '0.00'
    assert history(client, a)['total_records'] == 1 and history(client, b)['total_records'] == 0


def test_database_constraints_are_enforced(client, app):
    aid = account(client)
    with pytest.raises(IntegrityError), app.state.engine.begin() as connection:
        connection.execute(text('UPDATE accounts SET balance_cents = -1 WHERE id = :id'), {'id': aid})
    with pytest.raises(IntegrityError), app.state.engine.begin() as connection:
        connection.execute(text('UPDATE accounts SET balance_cents = 0.5 WHERE id = :id'), {'id': aid})
    with pytest.raises(IntegrityError), Session(app.state.engine) as session:
        session.add(Transaction(account_id=str(uuid4()), type='credit', amount_cents=100, reference_id='orphan'))
        session.commit()
    post(client, aid, reference='unique')
    with pytest.raises(IntegrityError), Session(app.state.engine) as session:
        session.add(Transaction(account_id=aid, type='credit', amount_cents=100, reference_id='unique'))
        session.commit()
    assert balance(client, aid) == '10.00'


def run_concurrently(count, operation):
    barrier = Barrier(count)
    def worker(index):
        barrier.wait(timeout=15)
        return operation(index)
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(worker, range(count)))


def test_concurrent_debits_cannot_overdraw(client):
    aid = account(client)
    post(client, aid, '100')
    results = run_concurrently(10, lambda i: post(client, aid, '30', 'debit', f'debit-{i}'))
    assert sorted(r.status_code for r in results) == [201] * 3 + [409] * 7
    assert balance(client, aid) == '10.00'
    assert history(client, aid)['total_records'] == 4


def test_concurrent_duplicate_is_applied_once(client):
    aid = account(client)
    results = run_concurrently(10, lambda _: post(client, aid, '10', reference='same'))
    assert sorted(r.status_code for r in results) == [201] + [409] * 9
    assert balance(client, aid) == '10.00'
    assert history(client, aid)['total_records'] == 1


def test_concurrent_transfers_preserve_total_funds(client):
    a, b = account(client), account(client, 'Bob')
    post(client, a, '100')
    results = run_concurrently(8, lambda i: transfer(client, a, b, '30', f'transfer-{i}'))
    assert sorted(r.status_code for r in results) == [201] * 3 + [409] * 5
    assert balance(client, a) == '10.00' and balance(client, b) == '90.00'
    assert history(client, a)['total_records'] == 4 and history(client, b)['total_records'] == 3


def test_file_database_persists_across_app_restart(tmp_path):
    url = f"sqlite:///{(tmp_path / 'persistent.db').as_posix()}"
    with TestClient(create_app(url)) as first:
        aid = account(first)
        post(first, aid, '12.34')
    with TestClient(create_app(url)) as second:
        assert balance(second, aid) == '12.34'
        assert history(second, aid)['total_records'] == 1
