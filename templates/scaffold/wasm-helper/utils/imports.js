export function buildImports() {
  return {
    env: {
      abort() {
        throw new Error("wasm abort");
      },
    },
  };
}
