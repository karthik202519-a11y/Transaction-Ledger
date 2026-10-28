export type Account = {
  id: string;
  name: string;
  balance: string;
  created_at: string;
};
export type Transaction = {
  id: string;
  account_id: string;
  type: "credit" | "debit";
  amount: string;
  description: string;
  reference_id: string;
  created_at: string;
  transfer_id: string | null;
};
export type History = {
  items: Transaction[];
  current_page: number;
  page_size: number;
  total_records: number;
  total_pages: number;
};

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new Error(
      "Could not reach the ledger. Check your connection and try again with the same reference ID.",
    );
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const details = payload?.error?.details
      ?.map(
        (item: { field: string; message: string }) =>
          `${item.field.replace("body.", "")}: ${item.message}`,
      )
      .join(" ");
    throw new Error(
      details ||
        payload?.error?.message ||
        `Request failed (${response.status}). Please try again.`,
    );
  }
  return payload as T;
}

export const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

// Formatting remains exact: never convert a monetary value through a float.
export function formatMoney(value: string) {
  const [whole, fraction = "00"] = value.split(".");
  return `${BigInt(whole).toLocaleString("en-US")}.${fraction.padEnd(2, "0")}`;
}
