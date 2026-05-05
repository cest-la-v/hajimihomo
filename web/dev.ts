// @ts-nocheck — run with `bun run dev.ts`
// Set RULESET_DIR env var to serve rulesets from a local build output:
//   RULESET_DIR=../dist bun run dev.ts
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

const rulesetDir = process.env.RULESET_DIR
  ? resolve(import.meta.dir, process.env.RULESET_DIR, "mihomo")
  : null;
const localRulesetsJson = rulesetDir
  ? await readFile(resolve(rulesetDir, "rulesets.json"), "utf8").catch(() => null)
  : null;

const CDN_RULESET = "https://cdn.jsdelivr.net/gh/cest-la-v/hajimihomo@ruleset/mihomo";

async function serveRulesetFile(pathname) {
  // Local file takes priority; fall back to CDN proxy
  if (rulesetDir) {
    const content = await readFile(resolve(rulesetDir, pathname), "utf8").catch(() => null);
    if (content) {
      const ct = pathname.endsWith(".json") ? "application/json" : "text/plain";
      return new Response(content, { headers: { "Content-Type": ct } });
    }
  }
  return fetch(`${CDN_RULESET}/${pathname}`);
}

Bun.serve({
  routes: {
    "/": index,
    "/presets.json": () => new Response(presetsJson, {
      headers: { "Content-Type": "application/json" },
    }),
    // Always intercept /ruleset/mihomo/* — local file or CDN proxy
    "/ruleset/mihomo/rulesets.json": () =>
      localRulesetsJson
        ? new Response(localRulesetsJson, { headers: { "Content-Type": "application/json" } })
        : fetch(`${CDN_RULESET}/rulesets.json`),
    "/ruleset/mihomo/*": (req) => {
      const pathname = new URL(req.url).pathname.replace("/ruleset/mihomo/", "");
      return serveRulesetFile(pathname);
    },
  },
  development: { hmr: true, console: true },
  port: 5173,
});

console.log("hajimihomo dev server → http://localhost:5173");
if (localRulesetsJson) console.log(`  rulesets: local ${rulesetDir}`);
else                   console.log("  rulesets: CDN proxy (set RULESET_DIR=../dist for local)");
