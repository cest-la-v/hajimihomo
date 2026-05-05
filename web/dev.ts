// @ts-nocheck — run with `bun run dev.ts`
import index from "./index.html";
import { readdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { load as parseYaml } from "js-yaml";

const presetsDir = resolve(import.meta.dir, "../profiles/presets");
const presets = {};
for (const file of (await readdir(presetsDir)).filter(f => f.endsWith(".yaml")).sort()) {
  const data = parseYaml(await readFile(resolve(presetsDir, file), "utf8")) || {};
  const name = data.name || file.replace(".yaml", "");
  presets[name] = { description: data.description || "", groups: data.groups || [] };
}
const presetsJson = JSON.stringify(presets, null, 2);

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
