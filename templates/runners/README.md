# 复现 Runner 模板索引

`templates/runners/` 说明每种复现形态的适用场景；`templates/scaffold/` 保存可以复制到 target 的最小代码骨架。

这些模板不代表结论。每个 target 仍然必须用浏览器样本、固定输入、本地输出和服务端验收结果验证。

## 路径选择

| Runner | 适用场景 | Scaffold | 默认落点 |
| --- | --- | --- | --- |
| `python-protocol` | 标准 hash/HMAC/AES、请求协议可直接还原 | `templates/scaffold/python-protocol/` | `targets/<site>/output/` |
| `node-protocol` | JS 算法可提取，但迁移到 Python 风险较高 | `templates/scaffold/node-protocol/` | `targets/<site>/output/` |
| `vm-sandbox` | 服务端下发 JS、动态 cookie/token、轻量浏览器对象依赖 | `templates/scaffold/vm-sandbox/` | `targets/<site>/scripts/env/` |
| `wasm-helper` | 参数来自 `.wasm` 导出、wasm wrapper 或 memory 编解码 | `templates/scaffold/wasm-helper/` | `targets/<site>/output/wasm-helper/` |
| `browser-auto-fallback` | 前面路径无法闭环，只能浏览器自动化兜底 | `templates/scaffold/browser-auto-fallback/` | `targets/<site>/output/browser-auto/` |

## 初始化命令

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-python -Runner python-protocol
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-node -Runner node-protocol
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-vm -Runner vm-sandbox
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-wasm -Runner wasm-helper
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-browser -Runner browser-auto-fallback
```

## 验收共识

1. 先固定浏览器样本，再写本地实现。
2. 本地输出必须和浏览器样本对齐。
3. 服务端响应不能只看 HTTP 状态码，必须看业务字段和数据完整性。
4. `browser-auto-fallback` 只作为兜底，并且默认 headless，失败后才 headed。
5. 真实目标 JS、HTML、WASM、字体、cookie、headers 和抓包样本放 `targets/<site>/`，不要放回模板目录。
