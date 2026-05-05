// @ts-nocheck — run with `bun run build.ts`
import { rm, writeFile } from "node:fs/promises";
import { $ } from "bun";

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

// Generate presets.json from profiles/presets/*.yaml via Python helper
const presetsJson = await $`python3 ../scripts/export_presets.py`.text();
await writeFile("dist/presets.json", presetsJson);

for (const output of result.outputs) {
  const rel = output.path.replace(process.cwd() + "/", "");
  console.log(`  ${rel}  ${(output.size / 1024).toFixed(1)} KB`);
}
console.log("  dist/presets.json");
