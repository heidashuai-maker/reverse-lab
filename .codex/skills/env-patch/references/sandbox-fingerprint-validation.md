# 沙箱验证与环境指纹比对

本文用于 `env-patch` 中“代码已经能在 Node/vm/jsdom 里执行，但签名、cookie、请求结果仍与浏览器不一致”的阶段。

核心判断：沙箱能生成值只是中间状态，只有浏览器真值、沙箱输出和服务端验收同时闭环，才算补环境完成。

## 触发条件

出现以下任一情况，必须进入本流程：

1. `env-diagnose.js` 显示 `success: true`，但签名长度、前缀、段数、编码或字段位置与浏览器样本不一致。
2. 本地能生成签名 / cookie，但真实接口返回空 body、少字段、业务错误码或静默失败。
3. 相同请求浏览器样本有效，本地沙箱样本无效。
4. 目标读取 `navigator/screen/document/canvas/webgl/audio/performance` 等指纹。
5. JSVMP、SDK 拦截器、WAF cookie 或动态 challenge 将环境值参与哈希。

## 七步闭环

### 1. 先确认入口和初始化链路

补环境前必须确认目标 JS 是否真的进入签名路径：

- 是导出函数直接调用，还是 XHR/fetch 拦截器“喂入-截出”。
- 是否需要 `init/setup/config/cacheOpts/paths` 等初始化参数。
- 目标 API 是否命中 SDK 的路径白名单。
- XHR 和 fetch 是否都需要覆盖，避免只 hook 一边。

如果 init 参数缺失，常见表现是 SDK 加载成功、hook 存在，但签名逻辑静默跳过。

### 2. 浏览器侧采集真值

优先用 Camoufox MCP 采集 Firefox 基准。目标明确是 Chrome 分支时，用 CloakBrowser MCP 采集 Chromium 基准。两类基准可以同时采，但不能混补。

采集内容至少包含：

- `navigator`：UA、platform、languages、plugins、webdriver、hardwareConcurrency、vendor、userAgentData / buildID。
- `screen/window`：screen、viewport、DPR、outer/inner、chrome 对象。
- `document/performance`：readyState、visibility、hasFocus、timing/navigation、performance.now。
- native 外形：`Function.prototype.toString`、`document.createElement.toString()`、`EventTarget.prototype.addEventListener.toString()`。
- 类型标签：`Object.prototype.toString.call(document/window/navigator/screen)`、`Symbol.toStringTag`。
- 指纹 API：Canvas、WebGL、AudioContext、DOM layout 尺寸。

### 3. 沙箱侧运行同一套探针

在本地 jsdom/vm 的目标上下文里执行完全相同的探针。jsdom 场景必须从 `win.eval()` 执行，不要在 Node 外层读值。

输出保存为：

- `browser-env-camoufox.json` 或 `browser-env-cloakbrowser.json`
- `local-env-baseline.json`
- `env-diff.json`

### 4. Diff 分级

按影响面分级，不要见差异就补。

| 等级 | 典型差异 | 处理 |
| --- | --- | --- |
| 致命 | native `toString` 暴露 jsdom、`plugins.length=0`、`webdriver` 异常、`document.hasFocus=false`、DOM layout 为 0 | 优先修 |
| 高危 | `Object.prototype.toString` 标签、`Symbol.toStringTag`、`window.chrome/userAgentData`、`performance.timing`、UA 家族不自洽 | 结合目标读取证据修 |
| 中危 | Worker、Notification、AudioContext、fetch、matchMedia、indexedDB、caches、visualViewport 等存在性 | 只有被读取或参与分支时修 |
| 低危 | 与目标链路无关的枚举顺序、冷门 API、未访问字段 | 记录但不补 |

### 5. 按最小因果单元补丁

每轮只补一个最小因果单元：

- 一个基础值，例如 `navigator.userAgent`。
- 一个函数壳，例如 `document.createElement`。
- 一个返回对象，例如 canvas context。
- 一个对象契约，例如 `PluginArray` / `Storage`。
- 一个 UA 家族外形，例如 Firefox native code 多行格式或 Chrome native code 单行格式。

补丁顺序建议：

1. `Function.prototype.toString` / native 外形。
2. `Symbol.toStringTag` 和对象类型标签。
3. `navigator` 基础字段、plugins/mimeTypes、webdriver。
4. `document` 状态、hasFocus、visibility。
5. DOM layout、Canvas、WebGL、Audio。
6. 目标读取过的中危 API stub。
7. 隐藏 Node.js 特征。

### 6. 沙箱内部验证

验证代码必须在目标看到的上下文中运行。最小验证项：

| 检查项 | 期望 |
| --- | --- |
| `document.createElement.toString()` | 与浏览器家族 native code 外形一致 |
| `navigator.plugins.length` | 与基准一致或至少非异常值 |
| `navigator.webdriver` | 与基准一致 |
| `document.hasFocus()` | 与基准一致 |
| `Object.prototype.toString.call(document)` | 与基准一致 |
| DOM `offsetWidth/offsetHeight` | 与基准或目标期望一致 |

验证通过后，再触发目标签名 / cookie / header 生成，与浏览器固定样本比较。

### 7. 服务端验收

必须使用真实接口验证，且不要把 HTTP 200 误判为成功。

成功标准：

- 目标字段能稳定生成。
- 浏览器样本和本地样本在格式、长度、编码、关键段上对齐。
- 真实接口返回有效业务数据。
- 至少连续 3 次成功；强时效签名建议连续 5 次。

失败判断：

- `HTTP 200 + 空 body`：通常是环境指纹不匹配或签名被降级接受。
- 返回字段变少：可能是风控态，不是成功态。
- 浏览器生成的签名在 Node/Python 请求里有效，本地沙箱签名无效：优先回到 env diff。
- 浏览器生成的签名也无法被 Node/Python 请求接受：检查 TLS、HTTP/2、header 顺序、cookie、IP/账号绑定。

## 禁动清单

没有证据证明目标读取时，不要默认改这些点：

1. 不要替换 `win.Error` 构造器。
2. 不要修改 `constructor.name` 来伪装对象类型。
3. 不要改 `Object.prototype` 或全局基础原型。
4. 不要把 `Symbol.toStringTag` 只设在实例上，应优先设在正确 prototype。
5. 不要二次覆盖 `Function.prototype.toString`；全局只保留一个统一实现。
6. 不要 Firefox UA 下补 Chrome-only API，也不要 Chrome UA 下补 Firefox-only API。
7. 不要批量补“看起来可能需要”的全套 API；以目标读取证据和 first divergence 为准。

## WASM 与无法补环境场景

如果动态字段来自 WASM：

1. 先分析 `.wasm` imports/exports。
2. 不要对缺失 import 自动塞空函数后直接验收。
3. 必须用浏览器固定输入验证导出函数输出。
4. 只把必要 wrapper、memory、string 编解码和 import 契约沉淀为 helper。

如果无法通过浏览器指纹补齐：

1. 判断是否缺少引擎级行为，例如真实布局、字体渲染、GPU、WebRTC、音频、行为轨迹。
2. 优先尝试协议侧或 TLS 指纹模拟。
3. 仍无法复现时，转浏览器自动化兜底，默认 headless，失败再 headed。
4. 在 notes 中写明为什么不是纯协议交付，以及后续可继续逆向的最小方向。
