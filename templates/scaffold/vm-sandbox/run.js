const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = __dirname;

function load(name) {
  return fs.readFileSync(path.join(root, name), "utf8");
}

function createSandbox() {
  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    Buffer,
    globalThis: {},
  };
  sandbox.window = sandbox.globalThis;
  sandbox.self = sandbox.globalThis;
  sandbox.global = sandbox.globalThis;
  vm.createContext(sandbox);
  for (const file of ["polyfills.js", "env.js", "entry.js"]) {
    vm.runInContext(load(file), sandbox, { filename: file });
  }
  return sandbox;
}

function selfTest() {
  const sandbox = createSandbox();
  if (typeof sandbox.globalThis.__reverseLabEntry !== "function") {
    console.error("Missing globalThis.__reverseLabEntry in entry.js");
    return 1;
  }
  const result = sandbox.globalThis.__reverseLabEntry({ path: "/api/demo", timestamp: "1700000000" });
  console.log(JSON.stringify({ success: true, result }, null, 2));
  return 0;
}

if (process.argv.includes("--self-test")) {
  process.exit(selfTest());
}

console.log("Usage: node run.js --self-test");
