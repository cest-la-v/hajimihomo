// @ts-nocheck — run with `bun run build.ts`
import { rm, writeFile, readdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { load as parseYaml } from "js-yaml";

await rm("dist", { recursive: true, force: true });

const result = await Bun.build({
  entrypoints: ["./index.html"],
  outdir: "dist",
  target: "browser",
  minify: true,
});

if (!result.success) {
  for (const msg of result.logs) console.error(msg);
  process.exit(1);
}

// Generate presets.json from profiles/presets/*.yaml
const presetsDir = resolve(import.meta.dir, "../profiles/presets");
const presets = {};
for (const file of (await readdir(presetsDir)).filter(f => f.endsWith(".yaml")).sort()) {
  const data = parseYaml(await readFile(resolve(presetsDir, file), "utf8")) || {};
  const name = data.name || file.replace(".yaml", "");
  presets[name] = { description: data.description || "", groups: data.groups || [] };
}
await writeFile("dist/presets.json", JSON.stringify(presets, null, 2));

for (const output of result.outputs) {
  const rel = output.path.replace(process.cwd() + "/", "");
  console.log(`  ${rel}  ${(output.size / 1024).toFixed(1)} KB`);
}
console.log("  dist/presets.json");
