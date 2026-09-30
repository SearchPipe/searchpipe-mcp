// Post-build step for the CJS bundle: tsc emits `dist/cjs/*.js`, we rename the
// emitted files to `.cjs` (so they are unambiguous CommonJS regardless of the
// package-level `"type": "module"`), rewrite the relative `require("./x.js")`
// specifiers accordingly, and drop a `dist/cjs/package.json` that pins
// `"type": "commonjs"` for the directory.
import { existsSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cjsDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "dist", "cjs");

if (!existsSync(cjsDir)) {
  console.error("fixup-cjs: dist/cjs is missing - run `tsc -p tsconfig.cjs.json` first");
  process.exit(1);
}

const requireSpecifier = /require\((["'])(\.[^"']*?)\.js\1\)/g;
let renamed = 0;

for (const entry of readdirSync(cjsDir)) {
  if (!entry.endsWith(".js")) continue;
  const source = path.join(cjsDir, entry);
  const target = path.join(cjsDir, entry.slice(0, -3) + ".cjs");
  const content = readFileSync(source, "utf8").replace(
    requireSpecifier,
    (_match, quote, specifier) => `require(${quote}${specifier}.cjs${quote})`
  );
  writeFileSync(target, content);
  rmSync(source);
  renamed += 1;
}

writeFileSync(
  path.join(cjsDir, "package.json"),
  JSON.stringify({ type: "commonjs" }, null, 2) + "\n"
);

console.log(`fixup-cjs: renamed ${renamed} file(s) to .cjs, wrote dist/cjs/package.json`);
