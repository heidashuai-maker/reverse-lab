# Browser-auto 兜底骨架

仅在纯协议、Node/vm/jsdom、WASM helper、TLS/HTTP 指纹路径都无法闭环后使用。默认 headless，失败后才切到 headed。

优先用 Camoufox MCP 或 CloakBrowser MCP 记录证据；这个 Node 版本只作为可运行兜底骨架。

## 验证

```powershell
npm install
node main.js --url "https://example.com"
```
