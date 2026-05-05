// @ts-nocheck — run with `bun run dev.ts`
import index from "./index.html";

Bun.serve({
  routes: {
    "/": index,
  },
  development: {
    hmr: true,
    console: true,
  },
  port: 5173,
});

console.log("hajimihomo dev server → http://localhost:5173");
