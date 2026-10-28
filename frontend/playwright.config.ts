import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import os from "node:os";

const databaseFile = path
  .join(os.tmpdir(), `ledger-browser-${Date.now()}.db`)
  .replaceAll("\\", "/");
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { open: "never" }],
    ["junit", { outputFile: "../docs/browser-tests.xml" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:5175",
    channel: process.env.PLAYWRIGHT_CHANNEL || "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `"${path.resolve("..", ".venv", "Scripts", "python.exe")}" -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8012`,
      url: "http://127.0.0.1:8012/health",
      reuseExistingServer: false,
      env: { LEDGER_DATABASE_URL: `sqlite:///${databaseFile}` },
    },
    {
      command: "npm run dev -- --port 5175",
      url: "http://127.0.0.1:5175",
      reuseExistingServer: false,
      env: { LEDGER_API_TARGET: "http://127.0.0.1:8012" },
    },
  ],
});
