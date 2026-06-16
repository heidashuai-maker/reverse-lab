export async function loadWasm(bytes, imports = {}) {
  const module = await WebAssembly.compile(bytes);
  const instance = await WebAssembly.instantiate(module, imports);
  return instance;
}
