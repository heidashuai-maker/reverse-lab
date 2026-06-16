// Narrow polyfills and diagnostics for local rebuild.
if (typeof globalThis.atob !== "function") {
  globalThis.atob = (value) => Buffer.from(String(value), "base64").toString("binary");
}

if (typeof globalThis.btoa !== "function") {
  globalThis.btoa = (value) => Buffer.from(String(value), "binary").toString("base64");
}
