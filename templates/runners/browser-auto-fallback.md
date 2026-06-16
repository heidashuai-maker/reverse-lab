# 浏览器自动化兜底模板

适用于纯协议、Node/vm/jsdom、WASM helper、TLS/HTTP 指纹模拟都无法闭环的目标。

推荐结构：

```text
output/browser-auto/
├── main.js
├── config.json
├── fixtures.json
├── screenshots/
└── README.md
```

准入条件：

1. 已记录为什么无法纯协议或本地 helper 复现。
2. 默认 `headless=true`，失败后才 `headless=false`。
3. 优先使用 Camoufox MCP；目标明确是 Chrome/Chromium 指纹分支时，可使用 CloakBrowser MCP。
4. 保存截图、关键网络请求、失败样本和成功样本。
5. README 必须写明这是 browser-auto 兜底，不是纯协议交付。
