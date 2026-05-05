// @ts-nocheck — run with `bun run dev.ts`
import index from "./index.html";
import { $ } from "bun";

const presetsJson = await $`python3 ../scripts/export_presets.py`.text();

Bun.serve({
  routes: {
    "/": index,
    "/presets.json": () => new Response(presetsJson, {
      headers: { "Content-Type": "application/json" },
    }),
  },
  development: {
    hmr: true,
    console: true,
  },
  port: 5173,
});

console.log("hajimihomo dev server → http://localhost:5173");
