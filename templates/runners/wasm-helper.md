# WASM helper 模板

适用于动态参数来自 `.wasm` 导出函数、wasm-bindgen wrapper、Emscripten 或 Go WASM 的目标。

推荐结构：

```text
output/wasm-helper/
├── main.js
├── load-wasm.js
├── imports.js
├── fixtures.json
└── README.md
```

最小要求：

1. 先用 `WebAssembly.Module.imports()` 和 `WebAssembly.Module.exports()` 记录 imports/exports。
2. 不要对未知 import 自动塞空函数后直接验收；关键 import 必须显式补全并解释来源。
3. 先用浏览器固定输入验证导出函数输出，再接真实请求。
4. 如果 wrapper 负责字符串、memory 或对象表转换，wrapper 也是协议的一部分，不能只调用裸导出。
5. WASM 文件和 wrapper 原始材料放 `source/`，helper 放 `output/wasm-helper/`。
