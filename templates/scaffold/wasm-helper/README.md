# WASM helper 骨架

用于动态参数来自 `.wasm` 导出函数、wasm-bindgen wrapper、Emscripten 或 Go WASM 的目标。

原始 `.wasm` 和 wrapper 放 `source/`；helper 放 `output/wasm-helper/`。先记录 imports/exports，再补 imports，不要用空函数掩盖缺失环境。

## 验证

```powershell
node output/wasm-helper/main.js --wasm ..\..\source\target.wasm
```
