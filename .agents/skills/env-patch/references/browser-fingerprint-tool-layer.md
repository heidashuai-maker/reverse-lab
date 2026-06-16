# 浏览器指纹工具层

本文定义 `env-patch` 在浏览器环境采集、差异比对和补环境验证时使用的工具层。目标不是把浏览器作为最终交付，而是用真实浏览器建立基准、证明差异、指导最小补丁。

## 工具定位

| 工具层 | 浏览器家族 | 主要用途 | 在本项目中的地位 |
| --- | --- | --- | --- |
| Camoufox MCP | Firefox / Gecko 指纹基准 | 环境真值采集、`compare_env`、运行时 hook、首屏挑战前置注入、Cookie 归因 | 默认首选工具层，环境差异分析必须优先考虑 |
| CloakBrowser MCP | Chrome / Chromium 指纹基准 | Chromium 源码级指纹、Playwright MCP 兼容自动化、Chrome 分支对照 | 可选工具层；当目标明确走 Chrome 特征或需要 Chromium 对照时启用 |
| DevTools / Playwright MCP / 浏览器插件 | 当前可用浏览器 | 基础页面观察、网络记录、临时 `evaluate` | 兜底工具层；能力不完整时要记录缺口 |

CloakBrowser MCP 是否可用以当前会话暴露的工具和本机诊断为准。使用前应运行 `cloakbrowser-mcp doctor --json` 或等价诊断确认本机可用。

## 基本原则

1. 浏览器工具用于采样、定位、对照和验收，不作为默认最终运行时。
2. Camoufox 采集到的是 Firefox 家族事实；CloakBrowser 采集到的是 Chrome/Chromium 家族事实，两者不能混补。
3. 补环境时必须先确定目标服务端或脚本实际接受哪一类 UA / 指纹分支。
4. 若浏览器样本能被 Node/Python HTTP 客户端复用并成功请求，说明问题大概率不在 TLS/HTTP 侧；若本地沙箱样本失败，应回到环境 diff。
5. 如果目标确实无法通过协议、Node/vm/jsdom、WASM 或 TLS 模拟复现，浏览器自动化可作为兜底路线，但必须记录不可移植原因。

## Camoufox MCP 基准流程

适用于 Firefox / Camoufox 指纹基准、强反检测页面和环境差异诊断。

1. 启动浏览器，优先无头；如果目标对 headless 敏感，再切有头。
2. 首轮导航不加 hook，读取状态码、重定向链、挑战页和真实业务请求。
3. 行为型签名可使用 `pre_inject_hooks` 或 `inject_hook_preset` 让 `xhr/fetch/cookie/runtime_probe` 在合适时机注入。
4. 使用 `compare_env` 采集粗粒度环境，再用 `evaluate_js` 分批采集细粒度环境。
5. 对 Cookie 使用组合证据区分 JS 写入和 HTTP `Set-Cookie`：`network_capture` / `list_network_requests` / `get_network_request` / `inject_hook_preset("cookie")` / `cookies`。
6. 对 JSVMP 使用 `hook_jsvmp_interpreter` 等低侵入探针优先，必要时再用 `instrumentation` 做源码级插桩。

推荐采集批次：

| 批次 | 内容 | 说明 |
| --- | --- | --- |
| A | `navigator` | UA、platform、languages、plugins、webdriver、hardwareConcurrency、vendor |
| B | `screen/window` | viewport、DPR、outer/inner、screen、chrome 对象是否存在 |
| C | `document/performance/toString` | readyState、visibility、Function native 字符串、`Object.prototype.toString` |
| D | DOM / Canvas / WebGL / Audio | layout 尺寸、canvas hash、WebGL vendor/renderer、AudioContext |
| E | Firefox 专项 | `navigator.buildID`、Firefox native code 多行格式、Firefox 独有 / 缺失 API |

## CloakBrowser MCP 基准流程

适用于目标明显走 Chrome/Chromium 特征，或需要和 Camoufox 结果做对照时。

1. 先确认本机 MCP 可用：`cloakbrowser-mcp doctor --json`。
2. 优先使用 Playwright MCP 兼容工具面完成 `navigate / snapshot / evaluate / storage` 等动作。
3. 采集与 Camoufox 完全相同的批次 A-D，额外记录 Chrome 专项：
   - `navigator.userAgentData`
   - `window.chrome`
   - `navigator.connection`
   - `performance.memory`
   - Chrome native code 单行格式
4. 若目标只在 Chrome 家族通过，补环境应以 CloakBrowser 基准为准，不要套用 Camoufox 的 Firefox 补丁。
5. 若目标只在 Camoufox 通过，则不要为了“看起来像 Chrome”补 `userAgentData/window.chrome`。

## UA 自洽矩阵

| 目标基准 | 必须保持 | 禁止混入 |
| --- | --- | --- |
| Firefox / Camoufox | Firefox UA、Firefox native code 多行格式、Firefox 支持的 API 集、`navigator.vendor` 等 Firefox 值 | `window.chrome`、`navigator.userAgentData`、Chrome-only `performance.memory`，除非有证据证明目标分支读取并接受 |
| Chrome / CloakBrowser | Chrome UA、Chrome native code 单行格式、`window.chrome`、`userAgentData`、Chrome Network Information API | Firefox-only `navigator.buildID`、`InstallTrigger` 等 |

## 浏览器自动化兜底

浏览器自动化不是默认交付，但允许作为最后兜底。进入兜底必须同时满足：

1. 真实请求和动态状态已经确认。
2. 纯 Python、纯 Node、Node vm/jsdom、WASM helper、TLS 指纹模拟均不可稳定复现。
3. 已记录失败原因，例如不可复制的人机验证、强交互行为模型、服务器绑定浏览器 profile、指纹动态挑战无法外移。
4. 自动化脚本优先无头；无头失败时再有头，并记录截图、网络证据、失败/成功样本。

兜底产物应放在 `targets/<site>/output/browser-auto/` 或等价目录，并在 `notes.md` 中明确它不是纯协议交付。

## 证据文件建议

环境比对相关材料写入当前目标目录，不写进 skill 目录：

```text
targets/<site>/
├── samples/
│   ├── browser-env-camoufox.json
│   ├── browser-env-cloakbrowser.json
│   ├── local-env-baseline.json
│   └── env-diff.json
├── scripts/env/
│   ├── collect-browser-env.js
│   ├── collect-local-env.js
│   ├── patch-plan.md
│   └── env-patch.js
└── notes.md
```

如果目标只做临时调查，等价文件可先放入 `js_reverse_cache/`，确认可复用后再沉淀到 `targets/<site>/`。
