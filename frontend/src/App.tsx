import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  ArrowRightLeft,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Plus,
  RefreshCw,
  Wallet,
} from "lucide-react";
import { type Account, type History, formatMoney, post, request } from "./api";

type Mode = "credit" | "debit" | "transfer";
const dateFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function AccountForm({
  onCreated,
  disabled,
  onBusy,
}: {
  onCreated: (account: Account) => void;
  disabled: boolean;
  onBusy: (busy: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const nameInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    nameInput.current?.focus();
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || busy || disabled) return;
    setBusy(true);
    onBusy(true);
    setError("");
    try {
      const account = await post<Account>("/api/accounts", {
        name: name.trim(),
      });
      setName("");
      onCreated(account);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      onBusy(false);
    }
  }
  return (
    <form
      onSubmit={submit}
      className="account-form"
      aria-label="Create account"
    >
      <label htmlFor="account-name">Account holder name</label>
      <input
        id="account-name"
        ref={nameInput}
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Account holder name"
        required
        maxLength={120}
        disabled={busy || disabled}
      />
      <button
        className="button primary"
        disabled={busy || disabled || !name.trim()}
      >
        <Plus size={16} />
        {busy ? "Creating…" : "Create account"}
      </button>
      <p className="hint">Every account starts with a 0.00 balance.</p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

function EntryForm({
  account,
  accounts,
  onSaved,
  onBusy,
  blocked,
}: {
  account: Account;
  accounts: Account[];
  onSaved: (message: string) => void;
  onBusy: (busy: boolean) => void;
  blocked: boolean;
}) {
  const [mode, setMode] = useState<Mode>("credit");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");
  const [destination, setDestination] = useState("");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState("");
  const destinations = accounts.filter((a) => a.id !== account.id);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busyRef.current || blocked) return;
    setError("");
    if (!/^\d+(\.\d{1,2})?$/.test(amount) || !/[1-9]/.test(amount)) {
      setError(
        "Enter an amount greater than zero with up to two decimal places.",
      );
      return;
    }
    if (!reference.trim()) {
      setError("Enter a reference ID for this transaction.");
      return;
    }
    if (mode === "transfer" && !destination) {
      setError("Choose a destination account.");
      return;
    }
    busyRef.current = true;
    setBusy(true);
    onBusy(true);
    try {
      const fields = {
        amount,
        reference_id: reference.trim(),
        description: description.trim(),
      };
      if (mode === "transfer") {
        await post("/api/transfers", {
          ...fields,
          source_account_id: account.id,
          destination_account_id: destination,
        });
      } else {
        await post(`/api/accounts/${account.id}/transactions`, {
          ...fields,
          type: mode,
        });
      }
      setAmount("");
      setReference("");
      setDescription("");
      onSaved(
        mode === "transfer"
          ? "Transfer completed. Both accounts have been updated."
          : `${mode === "credit" ? "Credit" : "Debit"} recorded successfully.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      busyRef.current = false;
      setBusy(false);
      onBusy(false);
    }
  }
  return (
    <aside className="entry-panel" aria-labelledby="entry-heading">
      <h2 id="entry-heading">New transaction</h2>
      <p className="muted">Record an entry for {account.name}.</p>
      <div className="segmented" aria-label="Transaction operation">
        {(["credit", "debit", "transfer"] as Mode[]).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={mode === value}
            disabled={busy || blocked}
            onClick={() => {
              setMode(value);
              setError("");
            }}
          >
            {value[0].toUpperCase() + value.slice(1)}
          </button>
        ))}
      </div>
      <form onSubmit={submit}>
        <fieldset disabled={busy || blocked}>
          {mode === "transfer" && (
            <div className="field">
              <label htmlFor="destination">To account</label>
              <select
                id="destination"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                required
              >
                <option value="">Select an account</option>
                {destinations.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} · {a.id.slice(0, 8)}
                  </option>
                ))}
              </select>
              {!destinations.length && (
                <p className="hint">
                  Create another account to make a transfer.
                </p>
              )}
            </div>
          )}
          <div className="field">
            <label htmlFor="amount">Amount</label>
            <input
              id="amount"
              inputMode="decimal"
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
              maxLength={13}
              autoComplete="off"
            />
            <p className="hint">Use up to two decimal places.</p>
          </div>
          <div className="field">
            <label htmlFor="reference">Reference ID</label>
            <input
              id="reference"
              placeholder="e.g. payment-001"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              required
              maxLength={120}
              autoComplete="off"
            />
            <p className="hint">
              A unique reference prevents duplicate entries.
            </p>
          </div>
          <div className="field">
            <label htmlFor="description">
              Description <span className="optional">Optional</span>
            </label>
            <textarea
              id="description"
              placeholder="What is this transaction for?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
              rows={3}
            />
          </div>
          {error && (
            <p className="form-error" role="alert">
              <CircleAlert size={17} />
              {error}
            </p>
          )}
          <button
            className="button primary submit"
            disabled={
              busy || blocked || (mode === "transfer" && !destinations.length)
            }
          >
            {mode === "transfer" ? (
              <ArrowRightLeft size={17} />
            ) : mode === "credit" ? (
              <ArrowDownLeft size={17} />
            ) : (
              <ArrowUpRight size={17} />
            )}
            {busy
              ? "Saving…"
              : mode === "transfer"
                ? "Transfer money"
                : `Record ${mode}`}
          </button>
        </fieldset>
      </form>
      <p className="entry-note">
        Entries are permanent. Review the amount and reference before saving.
      </p>
    </aside>
  );
}

export default function App() {
  const [view, setView] = useState<"ledger" | "create">("ledger");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selected, setSelected] = useState("");
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [history, setHistory] = useState<History | null>(null);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [notice, setNotice] = useState("");
  const account = accounts.find((a) => a.id === selected);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    request<Account[]>("/api/accounts", { signal: controller.signal })
      .then((items) => {
        setAccounts(items);
        setSelected((current) =>
          items.some((a) => a.id === current) ? current : items[0]?.id || "",
        );
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    if (!selected) {
      setHistory(null);
      return;
    }
    const controller = new AbortController();
    setHistoryLoading(true);
    setHistoryError("");
    setHistory(null);
    const query = new URLSearchParams({
      page: String(page),
      limit: String(limit),
    });
    if (filter) query.set("type", filter);
    request<History>(`/api/accounts/${selected}/transactions?${query}`, {
      signal: controller.signal,
    })
      .then(setHistory)
      .catch((e) => {
        if (!controller.signal.aborted) setHistoryError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setHistoryLoading(false);
      });
    return () => controller.abort();
  }, [selected, filter, page, limit, revision]);

  function choose(id: string) {
    setView("ledger");
    setSelected(id);
    setPage(1);
    setFilter("");
    setNotice("");
  }
  function created(newAccount: Account) {
    setAccounts((current) => [newAccount, ...current]);
    choose(newAccount.id);
    setNotice(`Account created for ${newAccount.name}.`);
    setRevision((r) => r + 1);
  }
  function saved(message: string) {
    setNotice(message);
    setPage(1);
    setRevision((r) => r + 1);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Ledger home">
          <span className="brand-mark">
            <BookOpen size={21} />
          </span>
          ledger<span className="brand-period">.</span>
        </a>
        <span className="workspace-label">Transaction workspace</span>
        <a className="docs-link" href="/docs" target="_blank" rel="noreferrer">
          API docs <ArrowUpRight size={14} />
        </a>
      </header>
      <div className="workspace">
        <aside className="accounts-panel" aria-label="Accounts">
          <div className="section-heading">
            <h2>Accounts</h2>
            <span className="count">{accounts.length}</span>
          </div>
          <p className="muted">A clear view of every balance.</p>
          {loading && !accounts.length ? (
            <p className="loading" role="status">
              Loading accounts…
            </p>
          ) : (
            <nav className="account-list" aria-label="Select an account">
              {accounts.map((a) => (
                <button
                  key={a.id}
                  className={`account-item ${a.id === selected ? "selected" : ""}`}
                  aria-current={a.id === selected ? "true" : undefined}
                  disabled={busy}
                  onClick={() => choose(a.id)}
                >
                  <span className="account-avatar">
                    {a.name.slice(0, 2).toUpperCase()}
                  </span>
                  <span className="account-copy">
                    <span className="account-name">{a.name}</span>
                    <span className="account-id">{a.id.slice(0, 8)}</span>
                    <span className="account-balance">
                      {formatMoney(a.balance)}
                    </span>
                  </span>
                  {a.id === selected && <span className="selection-dot" />}
                </button>
              ))}
            </nav>
          )}
          {!loading && !accounts.length && !error && (
            <p className="empty-accounts">Your accounts will appear here.</p>
          )}
          {accounts.length > 0 && (
            <label className="mobile-account-picker">
              Selected account
              <select
                aria-label="Selected account"
                value={selected}
                disabled={busy}
                onChange={(e) => choose(e.target.value)}
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} · {a.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="sidebar-footer">
            <BookOpen size={15} />
            <span>Every entry, accounted for.</span>
          </div>
        </aside>
        <main>
          <div className="page-heading">
            <div>
              <h1>{view === "create" ? "Create account" : "Account ledger"}</h1>
              <p className="muted">
                {view === "create"
                  ? "Add an account to your ledger."
                  : "Follow the money. Keep the full story."}
              </p>
            </div>
            <div className="header-actions">
              {view === "ledger" ? (
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => {
                    setView("create");
                    setNotice("");
                  }}
                >
                  <Plus size={16} />
                  Create account
                </button>
              ) : (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => setView("ledger")}
                >
                  <ChevronLeft size={16} />
                  Back to ledger
                </button>
              )}
              <button
                className="button refresh"
                aria-label="Refresh ledger"
                disabled={loading || busy}
                onClick={() => setRevision((r) => r + 1)}
              >
                <RefreshCw size={16} />
                <span>Refresh</span>
              </button>
            </div>
          </div>
          {error && (
            <div className="banner error" role="alert">
              <CircleAlert size={19} />
              <span>{error} Use Refresh to retry.</span>
            </div>
          )}
          {notice && (
            <div className="banner success" role="status">
              <CheckCircle2 size={18} />
              <span>{notice}</span>
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                Dismiss
              </button>
            </div>
          )}
          {view === "create" ? (
            <section
              className="create-account-panel"
              aria-label="Account details"
            >
              <h2>Account details</h2>
              <p className="muted">
                Enter the name of the person or business this account belongs
                to.
              </p>
              <AccountForm
                onCreated={created}
                disabled={busy}
                onBusy={setBusy}
              />
            </section>
          ) : account ? (
            <>
              <section
                className="balance-strip"
                aria-label="Selected account balance"
              >
                <div className="balance-identity">
                  <span className="wallet-symbol">
                    <Wallet size={25} />
                  </span>
                  <div>
                    <h2>{account.name}</h2>
                    <span className="full-id">{account.id}</span>
                    <p>
                      Opened{" "}
                      {new Date(account.created_at).toLocaleDateString(
                        undefined,
                        { dateStyle: "medium" },
                      )}
                    </p>
                  </div>
                </div>
                <div className="balance-amount">
                  <span>Available balance</span>
                  <strong data-testid="balance">
                    {formatMoney(account.balance)}
                  </strong>
                  <span>Account units</span>
                </div>
              </section>
              <a
                className="mobile-entry-link button secondary"
                href="#entry-heading"
              >
                <Plus size={16} />
                New transaction
              </a>
              <div className="ledger-layout">
                <section
                  className="history-panel"
                  aria-labelledby="history-heading"
                >
                  <div className="history-heading">
                    <div>
                      <h2 id="history-heading">Transaction history</h2>
                      <p className="muted">
                        {history
                          ? `${history.total_records} ${history.total_records === 1 ? "entry" : "entries"}${filter ? ` · ${filter} only` : ""}`
                          : "Your complete account activity"}
                      </p>
                    </div>
                    <label className="filter-label">
                      Show
                      <select
                        aria-label="Filter transactions"
                        value={filter}
                        onChange={(e) => {
                          setFilter(e.target.value);
                          setPage(1);
                        }}
                      >
                        <option value="">All transactions</option>
                        <option value="credit">Credits</option>
                        <option value="debit">Debits</option>
                      </select>
                    </label>
                  </div>
                  {historyLoading ? (
                    <div className="history-state" role="status">
                      Loading transactions…
                    </div>
                  ) : historyError ? (
                    <div className="history-state form-error" role="alert">
                      {historyError}
                      <button
                        className="button secondary"
                        onClick={() => setRevision((r) => r + 1)}
                      >
                        Retry history
                      </button>
                    </div>
                  ) : history?.items.length ? (
                    <>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th scope="col">Transaction</th>
                              <th scope="col">Reference / Date</th>
                              <th scope="col" className="amount-cell">
                                Amount
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {history.items.map((t) => (
                              <tr key={t.id}>
                                <td>
                                  <div className="transaction-cell">
                                    <span
                                      className={`transaction-icon ${t.type}`}
                                    >
                                      {t.type === "credit" ? (
                                        <ArrowDownLeft size={18} />
                                      ) : (
                                        <ArrowUpRight size={18} />
                                      )}
                                    </span>
                                    <div>
                                      <span className="transaction-title">
                                        {t.description ||
                                          (t.transfer_id
                                            ? "Account transfer"
                                            : t.type === "credit"
                                              ? "Credit received"
                                              : "Debit recorded")}
                                      </span>
                                      <span className={`type-label ${t.type}`}>
                                        {t.type}
                                        {t.transfer_id ? " · transfer" : ""}
                                      </span>
                                    </div>
                                  </div>
                                </td>
                                <td>
                                  <span className="reference">
                                    {t.reference_id}
                                  </span>
                                  <time dateTime={t.created_at}>
                                    {dateFormat.format(new Date(t.created_at))}
                                  </time>
                                </td>
                                <td
                                  className={`amount-cell transaction-amount ${t.type}`}
                                >
                                  {t.type === "credit" ? "+" : "−"}
                                  {formatMoney(t.amount)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  ) : (
                    <div className="history-state">
                      <BookOpen size={31} strokeWidth={1.4} />
                      <h3>
                        {filter
                          ? `No ${filter} entries yet`
                          : "A fresh start for this account"}
                      </h3>
                      <p>
                        {filter
                          ? "Choose all transactions to see the full history."
                          : "Record your first credit to start the ledger. Every entry will appear here."}
                      </p>
                    </div>
                  )}
                  <div className="pagination">
                    <label>
                      Rows
                      <select
                        aria-label="Rows per page"
                        value={limit}
                        onChange={(e) => {
                          setLimit(Number(e.target.value));
                          setPage(1);
                        }}
                      >
                        <option value={10}>10</option>
                        <option value={25}>25</option>
                        <option value={50}>50</option>
                      </select>
                    </label>
                    <span>
                      {history
                        ? `Page ${history.total_pages ? page : 0} of ${history.total_pages}`
                        : "—"}
                    </span>
                    <div>
                      <button
                        className="page-button"
                        aria-label="Previous page"
                        disabled={page <= 1 || historyLoading}
                        onClick={() => setPage((p) => p - 1)}
                      >
                        <ChevronLeft size={17} />
                      </button>
                      <button
                        className="page-button"
                        aria-label="Next page"
                        disabled={
                          !history ||
                          page >= history.total_pages ||
                          historyLoading
                        }
                        onClick={() => setPage((p) => p + 1)}
                      >
                        <ChevronRight size={17} />
                      </button>
                    </div>
                  </div>
                </section>
                <EntryForm
                  key={account.id}
                  account={account}
                  accounts={accounts}
                  onSaved={saved}
                  onBusy={setBusy}
                  blocked={busy}
                />
              </div>
            </>
          ) : !loading && !error ? (
            <section className="welcome">
              <span className="welcome-icon">
                <BookOpen size={42} strokeWidth={1.3} />
              </span>
              <h2>Good records start here.</h2>
              <p>
                Create your first account to record credits, manage debits, and
                see every transaction in one place.
              </p>
              <button
                className="button primary"
                onClick={() => setView("create")}
              >
                <Plus size={17} />
                Create your first account
              </button>
              <div className="welcome-details">
                <span>Exact balances</span>
                <span>Permanent history</span>
                <span>Simple transfers</span>
              </div>
            </section>
          ) : null}
          <footer className="main-footer">
            <span>Transaction Ledger</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
