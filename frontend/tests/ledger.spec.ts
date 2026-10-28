import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import AxeBuilder from "@axe-core/playwright";

async function selectAccount(page: Page, name: string) {
  const picker = page.getByLabel("Selected account", { exact: true });
  if (await picker.isVisible()) {
    const option = picker.locator("option").filter({ hasText: name });
    await picker.selectOption((await option.getAttribute("value")) || "");
  } else {
    await page.getByRole("button", { name: new RegExp(name) }).click();
  }
}

async function createAccount(page: Page, name: string) {
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.getByLabel("Account holder name", { exact: true }).fill(name);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByTestId("balance")).toHaveText("0.00");
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}

async function record(
  page: Page,
  type: "Credit" | "Debit",
  amount: string,
  reference: string,
  description = "",
) {
  await page.getByRole("button", { name: type, exact: true }).click();
  await page.getByLabel("Amount", { exact: true }).fill(amount);
  await page.getByLabel("Reference ID", { exact: true }).fill(reference);
  await page.getByLabel("Description").fill(description);
  await page
    .getByRole("button", { name: `Record ${type.toLowerCase()}`, exact: true })
    .click();
}

test("header account creation supports cancel, validation and retry", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Create account", exact: true }),
  ).toBeVisible();
  const name = page.getByLabel("Account holder name", { exact: true });
  await expect(name).toBeFocused();
  await name.fill("   ");
  await expect(
    page.getByRole("button", { name: "Create account", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Back to ledger" }).click();
  await expect(
    page.getByRole("heading", { name: "Account ledger", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  const accountName = `New header account ${testInfo.project.name}`;
  await name.fill(accountName);
  await page.route("**/api/accounts", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({
          status: 503,
          json: {
            error: {
              message: "Could not create account. Try again.",
              details: [],
            },
          },
        })
      : route.continue(),
  );
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Could not create account",
  );
  await expect(name).toHaveValue(accountName);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  fs.mkdirSync("test-results/screenshots", { recursive: true });
  await page.screenshot({
    path: `test-results/screenshots/create-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.unroute("**/api/accounts");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Account ledger", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: accountName, exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("balance")).toHaveText("0.00");
});

test("complete ledger workflow, validations, duplicate protection, transfer and responsive layout", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const suffix = `${testInfo.project.name}-${Date.now()}`;
  const alice = `Operating account ${suffix}`;
  const bob = `Reserve account ${suffix}`;
  await page.goto("/");
  await createAccount(page, alice);
  await expect(page.getByText("A fresh start for this account")).toBeVisible();

  await record(
    page,
    "Credit",
    "100.25",
    `opening-${suffix}`,
    "Opening balance",
  );
  await expect(page.getByTestId("balance")).toHaveText("100.25");
  await expect(
    page.getByRole("cell", { name: "Opening balance credit" }),
  ).toBeVisible();

  await record(page, "Credit", "100.25", `opening-${suffix}`);
  await expect(page.getByRole("alert")).toContainText("already exists");
  await expect(page.getByTestId("balance")).toHaveText("100.25");

  await record(page, "Debit", "200", `rejected-${suffix}`);
  await expect(page.getByRole("alert")).toContainText("sufficient balance");
  await expect(page.getByTestId("balance")).toHaveText("100.25");

  await record(page, "Credit", "0.001", `precision-${suffix}`);
  await expect(page.getByRole("alert")).toContainText("two decimal places");

  await record(page, "Debit", "20.25", `expense-${suffix}`, "Office supplies");
  await expect(page.getByTestId("balance")).toHaveText("80.00");
  await page.getByLabel("Filter transactions").selectOption("debit");
  await expect(
    page.getByRole("cell", { name: "Office supplies debit" }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Opening balance credit" }),
  ).toHaveCount(0);

  await createAccount(page, bob);
  await selectAccount(page, alice);
  await expect(page.getByTestId("balance")).toHaveText("80.00");
  await page.getByRole("button", { name: "Transfer", exact: true }).click();
  await page.getByLabel("To account").selectOption({
    label:
      (await page
        .getByLabel("To account")
        .locator("option")
        .filter({ hasText: bob })
        .textContent()) || "",
  });
  await page.getByLabel("Amount", { exact: true }).fill("30");
  await page.getByLabel("Reference ID", { exact: true }).fill(`move-${suffix}`);
  await page.getByLabel("Description").fill("Reserve allocation");
  await page
    .getByRole("button", { name: "Transfer money", exact: true })
    .click();
  await expect(page.getByTestId("balance")).toHaveText("50.00");
  await selectAccount(page, bob);
  await expect(page.getByTestId("balance")).toHaveText("30.00");
  await expect(
    page.getByRole("cell", { name: "Reserve allocation credit · transfer" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("balance")).toHaveText("30.00");
  await expect(
    page.getByRole("heading", { name: bob, exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("pagination, retry states and screenshot evidence", async ({
  page,
  request,
}, testInfo) => {
  const account = await (
    await request.post("/api/accounts", {
      data: { name: `Northwind operations ${testInfo.project.name}` },
    })
  ).json();
  for (let i = 0; i < 12; i++) {
    const result = await request.post(
      `/api/accounts/${account.id}/transactions`,
      {
        data: {
          type: i % 3 ? "credit" : "debit",
          amount: i === 0 ? "0.01" : "10",
          reference_id: `entry-${i}`,
          description: `Ledger entry ${i}`,
        },
      },
    );
    // First entry is an intentionally rejected debit; the next eleven succeed.
    expect(result.status()).toBe(i === 0 ? 409 : 201);
  }
  await page.goto("/");
  await expect(page.getByText("Page 1 of 2")).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(10);
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page.getByText("Page 2 of 2")).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("button", { name: "Previous page" }).click();
  await page.getByLabel("Rows per page").selectOption("25");
  await expect(page.locator("tbody tr")).toHaveCount(11);

  await page.route("**/api/accounts/*/transactions?*", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { message: "Temporary test failure", details: [] } },
    }),
  );
  await page.getByRole("button", { name: "Refresh ledger" }).click();
  await expect(page.getByRole("alert")).toContainText("Temporary test failure");
  await page.unroute("**/api/accounts/*/transactions?*");
  await page.getByRole("button", { name: "Retry history" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(11);
  await page.getByLabel("Rows per page").selectOption("10");
  await expect(page.locator("tbody tr")).toHaveCount(10);
  await page.evaluate(() => document.fonts.ready);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  fs.mkdirSync("test-results/screenshots", { recursive: true });
  await page.screenshot({
    path: `test-results/screenshots/${testInfo.project.name.startsWith("mobile") ? "mobile" : "desktop"}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("account loading error recovers and transaction request disables repeated submit", async ({
  page,
}) => {
  await page.route("**/api/accounts", (route) =>
    route.request().method() === "GET"
      ? route.fulfill({
          status: 503,
          json: {
            error: { message: "Ledger temporarily unavailable", details: [] },
          },
        })
      : route.continue(),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Ledger temporarily unavailable",
  );
  await page.unroute("**/api/accounts");
  await page.getByRole("button", { name: "Refresh ledger" }).click();
  await createAccount(page, `Pending request ${Date.now()}`);
  let release!: () => void;
  const waitForRelease = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/accounts/*/transactions", async (route) => {
    if (route.request().method() === "POST") await waitForRelease;
    await route.continue();
  });
  await record(page, "Credit", "10", "once");
  await expect(page.getByRole("button", { name: "Saving…" })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Create account", exact: true }),
  ).toBeDisabled();
  release();
  await expect(page.getByTestId("balance")).toHaveText("10.00");
  await expect(page.locator("tbody tr")).toHaveCount(1);
});
