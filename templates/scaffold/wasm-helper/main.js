import fs from "node:fs";
import { loadWasm } from "./utils/load-wasm.js";
import { buildImports } from "./utils/imports.js";

function getArg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : "";
}

const wasmPath = getArg("--wasm");
if (!wasmPath) {
  console.log("Usage: node main.js --wasm <path-to-wasm>");
  process.exit(0);
}

const bytes = fs.readFileSync(wasmPath);
const module = await WebAssembly.compile(bytes);
console.log("imports:", WebAssembly.Module.imports(module));
console.log("exports:", WebAssembly.Module.exports(module));

const instance = await loadWasm(bytes, buildImports());
console.log("loaded exports:", Object.keys(instance.exports));
