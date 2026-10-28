import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": process.env.LEDGER_API_TARGET || "http://127.0.0.1:8000",
      "/health": process.env.LEDGER_API_TARGET || "http://127.0.0.1:8000",
      "/docs": process.env.LEDGER_API_TARGET || "http://127.0.0.1:8000",
      "/openapi.json": process.env.LEDGER_API_TARGET || "http://127.0.0.1:8000",
    },
  },
});
