// @ts-nocheck — run with `bun run dev.ts`
// Set RULESET_DIR env var to serve rulesets.json from a local build output:
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

// Optional: serve local rulesets.json instead of CDN
const rulesetDir = process.env.RULESET_DIR
  ? resolve(import.meta.dir, process.env.RULESET_DIR, "mihomo")
  : null;
const localRulesetsJson = rulesetDir
  ? await readFile(resolve(rulesetDir, "rulesets.json"), "utf8").catch(() => null)
  : null;
if (localRulesetsJson) console.log(`Local rulesets.json loaded from ${rulesetDir}`);

Bun.serve({
  routes: {
    "/": index,
    "/presets.json": () => new Response(presetsJson, {
      headers: { "Content-Type": "application/json" },
    }),
    // Proxy rule files from local build output when RULESET_DIR is set
    ...(rulesetDir && {
      "/ruleset/mihomo/*": async (req) => {
        const path = new URL(req.url).pathname.replace("/ruleset/mihomo/", "");
        const content = await readFile(resolve(rulesetDir, path), "utf8").catch(() => null);
        if (!content) return new Response("Not found", { status: 404 });
        const ct = path.endsWith(".json") ? "application/json" : "text/plain";
        return new Response(content, { headers: { "Content-Type": ct } });
      },
      "/ruleset/mihomo/rulesets.json": () => new Response(localRulesetsJson, {
        headers: { "Content-Type": "application/json" },
      }),
    }),
  },
  development: {
    hmr: true,
    console: true,
  },
  port: 5173,
});

console.log("hajimihomo dev server → http://localhost:5173");
if (rulesetDir) console.log(`  rule files: local ${rulesetDir}`);
else            console.log("  rule files: CDN (set RULESET_DIR=../dist to use local build)");
