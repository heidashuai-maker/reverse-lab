# 复现路径分流矩阵

本文用于选择最终复现形态。原则是协议优先，但不把“无法纯协议复现”的目标强行伪装成已完成协议恢复。

## 优先级

```text
纯 Python 协议还原
→ 纯 Node.js 协议还原
→ Node.js vm / jsdom / sdenv 补环境
→ WASM helper
→ TLS / HTTP 指纹模拟
→ 浏览器自动化兜底：优先 headless，其次 headed
```

## 路径选择

| 路径 | 适用场景 | 交付形态 | 不适用信号 |
| --- | --- | --- | --- |
| 纯 Python | 标准 hash/HMAC/AES/RSA、参数拼接、响应解码、HTTP 状态可独立维护 | `output/main.py` | 依赖大量浏览器对象、JSVMP、WASM memory |
| 纯 Node.js | JS 算法可提取，但移植 Python 成本高 | `output/main.js` 或 Python 调 Node helper | 需要真实 DOM/layout/GPU/字体 |
| Node vm/jsdom/sdenv | 服务端下发 JS、动态 cookie、JSVMP 可在本地跑通 | `scripts/env/run.js` + helper | 环境 diff 无法收敛、服务端持续静默拒绝 |
| WASM helper | 参数来自 `.wasm` 导出或 wasm wrapper | `output/wasm-helper/` | imports 无法显式补全、输出无法对齐浏览器固定样本 |
| TLS / HTTP 指纹模拟 | 浏览器值可用，但 Node/Python 请求失败 | `curl_cffi` / `got-scraping` / HTTP2 helper | 浏览器值本身也不被服务端接受 |
| 浏览器自动化兜底 | 行为模型、人机验证、引擎级指纹、动态 profile 绑定无法外移 | `output/browser-auto/` | 只是未完成逆向、没有做前面路径验证 |

## 浏览器工具基准

| 工具 | 用途 |
| --- | --- |
| Camoufox MCP | Firefox/Gecko 指纹基准，环境差异、hook、Cookie 归因、服务端验收 |
| CloakBrowser MCP | Chrome/Chromium 指纹基准，Chrome 分支对照，Playwright MCP 兼容自动化 |

Camoufox 和 CloakBrowser 的环境样本要分开存放，不能混用。补环境时以目标实际接受的 UA / 指纹分支为准。

## 浏览器自动化兜底准入

只有满足以下条件，才允许把浏览器自动化作为交付形态：

1. 已确认真实请求、动态字段和关键脚本。
2. 已尝试或明确排除纯 Python、纯 Node、vm/jsdom、WASM helper、TLS/HTTP 指纹模拟。
3. 已记录阻塞原因，例如行为模型、验证码、人机验证、引擎级渲染/字体/GPU、浏览器 profile 绑定。
4. 自动化脚本默认 `headless=true`；无头失败再切 `headless=false`。
5. 产物必须记录运行成本、失败模式、截图/网络证据和后续可继续逆向的最小方向。

兜底不是“逆向完成”，而是“当前证据下可执行的工程折中”。在 `notes.md` 中必须明确标注。
