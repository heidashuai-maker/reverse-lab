# jsdom / vm 环境伪装专项 Playbook

本文用于 `env-patch` 中的深度沙箱补环境场景：目标 JS 已经能在 Node.js、`vm`、`jsdom` 或 `sdenv` 中加载，但生成的 sign、cookie、header、URL 参数或 WAF challenge 输出与浏览器不一致，且证据显示环境指纹参与计算。

它吸收 `tmp/hello_js_reverse_skill-main` 中路径 B 的可靠经验，但使用当前 reverse-lab 的工具名、证据契约和项目目录约定重写。不要把本文理解为“浏览器大全补丁清单”；每个补丁都必须能回溯到 Camoufox/CloakBrowser 真值、runtime trace、env diff 或 first divergence。

## 适用条件

优先进入本文，当满足以下任一条件：

- JSVMP / 安全 SDK / WAF runtime 读取 `navigator`、`document`、`screen`、Canvas、WebGL、Audio、`performance`、native `toString` 等环境值。
- 入口已知，但算法被 VM 字节码或 SDK 黑箱包住，直接提取纯算法成本高。
- 目标通过 XHR/fetch 拦截器追加签名，适合“喂入-截出”。
- 本地沙箱能生成输出，但浏览器样本可用、本地样本被服务端静默拒绝。
- `HTTP 200 + 空 body`、字段少、业务错误码、签名长度正确但不可用，且请求契约本身已排除。
- `compare_env` 或 `trace_property_access` 显示目标读取过高风险环境属性。

不要进入本文，当：

- 签名入口、初始化参数、目标请求还没确认。先回 `find-crypto-entry` 或 `env-patch` 步骤 0。
- 只是缺少少量全局对象，`env-diagnose.js` + `env/` 模块树即可修复。
- 目标更像 TLS/HTTP 指纹、账号/IP 风控、频率限制或服务端会话绑定。
- 用户最终目标是 Python + iv8 复现，应转 `iv8-web-reverse` 或更窄 adapter。

## 路线总览

```text
0. 确认入口和初始化链路
1. 用 Camoufox/CloakBrowser 采集浏览器真值
2. 在 jsdom/vm/sdenv 中运行同一套探针
3. 生成 env diff 并按影响分级
4. 写最小环境补丁
5. 在沙箱内部验证补丁外形
6. 触发目标输出并做服务端验收
```

核心原则：

- 先确认入口，再补环境。
- 同一套探针同时跑浏览器和本地沙箱。
- 先修致命差异，再修被真实读取过的高危差异。
- 每轮只补一个最小因果单元。
- 不把 Camoufox 的 Firefox 事实和 CloakBrowser 的 Chrome 事实混补。
- 不把浏览器自动化作为最终签名/cookie 生成方案。

## 0. 确认入口和初始化链路

补环境前必须确认目标 JS 真的进入签名路径。否则会出现“环境补了很多，但签名逻辑根本没触发”的假进展。

至少确认：

- 入口类型：导出函数、XHR 拦截、fetch 拦截、动态 cookie writer、challenge runner、webpack module。
- 初始化函数：`init`、`setup`、`config`、`cacheOpts`、`paths`、`_SdkGlueInit`、白名单 URL。
- 通道覆盖：只拦 XHR，还是 XHR + fetch 双通道。
- 输出消费点：URL 参数、header、body 字段、cookie、storage、内存槽位。
- 触发动作：页面加载、点击、翻页、搜索、预热请求、challenge 二跳。

推荐 Camoufox 操作：

```text
network_capture(action="start", capture_body=true)
navigate(url="<target>", pre_inject_hooks=["xhr","fetch","cookie"])
list_network_requests(...)
get_network_request(...)
get_request_initiator(...)
scripts(action="list")
search_code(keyword="init|setup|cacheOpts|XMLHttpRequest|fetch|sign|token")
evaluate_js("(() => { return {...}; })()")
```

常见判定：

| 证据 | 结论 | 后续 |
| --- | --- | --- |
| 只有导出函数 | 可直接调用 | 固定输入调用函数，对齐浏览器输出 |
| 劫持 XHR | 喂入-截出 | 在沙箱内发 XHR，截最终 URL/header |
| 劫持 fetch | fetch 喂入-截出 | hook `fetch` 入参和返回 Promise |
| `cacheOpts` / path 白名单 | 初始化驱动 | 必须传入同浏览器配置 |
| SDK 加载时保存原型引用 | 补丁要早 | 环境补丁和 hook 必须早于 SDK |

## 1. 浏览器真值采集

优先用 Camoufox 采 Firefox/Gecko 基准；目标明确只接受 Chrome/Chromium 指纹分支时，用 CloakBrowser 采 Chrome 基准。两者可以都采，但必须分文件保存。

建议产物：

```text
targets/<site>/samples/browser-env-camoufox.json
targets/<site>/samples/browser-env-cloakbrowser.json
targets/<site>/samples/browser-state-camoufox.json
targets/<site>/samples/env-read-trace.jsonl
targets/<site>/samples/runtime-evidence.jsonl
```

最小流程：

1. `check_environment` 记录工具可用性。
2. `network_capture` + `navigate` 得到真实请求和页面状态。
3. `compare_env` 得到粗粒度基准。
4. `evaluate_js` 分批采集细粒度值。
5. `cookies`、`get_storage`、`export_state` 保存状态。
6. 强环境检测时优先 `trace_property_access` 或 `instrumentation`，确认真实读取项。

### 分批 evaluate_js 采集

单次 `evaluate_js` 代码过长容易失败，也容易返回不可序列化对象。统一使用 IIFE，并只返回 JSON 可序列化数据：

```javascript
(() => {
  return {
    userAgent: navigator.userAgent,
    platform: navigator.platform
  };
})()
```

#### 批次 A：navigator

采集：

- `userAgent`
- `platform`
- `language`
- `languages`
- `cookieEnabled`
- `doNotTrack`
- `hardwareConcurrency`
- `maxTouchPoints`
- `vendor`
- `vendorSub`
- `productSub`
- `appVersion`
- `appName`
- `appCodeName`
- `onLine`
- `webdriver`
- `pdfViewerEnabled`
- `deviceMemory`
- `plugins.length`
- `mimeTypes.length`
- `connection.effectiveType/downlink/rtt/saveData`
- `userAgentData.brands/mobile/platform/getHighEntropyValues`
- `typeof navigator.getBattery`
- `typeof navigator.mediaDevices`

#### 批次 B：screen + window

采集：

- `screen.width/height/availWidth/availHeight`
- `screen.colorDepth/pixelDepth`
- `screen.orientation.type/angle`
- `innerWidth/innerHeight`
- `outerWidth/outerHeight`
- `devicePixelRatio`
- `screenX/screenY/screenLeft/screenTop`
- `typeof window.chrome`
- `typeof window.chrome.runtime`
- `typeof Notification`
- `typeof Worker`
- `typeof SharedWorker`
- `typeof RTCPeerConnection`
- `typeof AudioContext`
- `typeof OfflineAudioContext`
- `typeof fetch`
- `typeof matchMedia`
- `typeof indexedDB`
- `typeof caches`
- `typeof visualViewport`
- `isSecureContext`

#### 批次 C：document + performance + native 外形

采集：

- `document.hasFocus()`
- `document.readyState`
- `document.visibilityState`
- `document.hidden`
- `document.characterSet`
- `document.compatMode`
- `document.contentType`
- `document.referrer`
- `document.domain`
- `typeof document.cookie`
- `typeof performance.timing`
- `typeof performance.navigation`
- `typeof performance.now`
- `typeof performance.memory`
- `document.createElement.toString()`
- `document.getElementById.toString()`
- `document.querySelector.toString()`
- `EventTarget.prototype.addEventListener.toString()`
- `window.fetch && window.fetch.toString()`
- `window.setTimeout.toString()`
- `Object.prototype.toString.call(document/window/navigator/screen/performance)`
- `document[Symbol.toStringTag]`
- `screen[Symbol.toStringTag]`

#### 批次 D：DOM layout + Canvas + WebGL + Audio

采集思路：

- 创建一个带 `width/height` 的 `div`，读取 `offsetWidth/offsetHeight/clientWidth/clientHeight/getBoundingClientRect()`。
- 创建 canvas，写入固定文字，记录 `toDataURL()` 长度或 hash，不要在报告中存大体积原始图像。
- 读取 WebGL `VENDOR/RENDERER/VERSION`，必要时读 `WEBGL_debug_renderer_info`。
- 记录 `AudioContext` / `OfflineAudioContext` 是否存在，以及固定探针摘要。

## 2. 本地沙箱同探针采集

jsdom 场景必须在 `win.eval()` 中执行同一套探针，不要从 Node 外层读取值。目标代码看到的是 jsdom window 上下文，外层读值会掩盖 cross-realm 差异。

最小 jsdom 骨架：

```javascript
const { JSDOM } = require("jsdom");

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: targetUrl,
  referrer: referrer || "",
  contentType: "text/html",
  pretendToBeVisual: true,
  runScripts: "dangerously",
  resources: "usable"
});

const win = dom.window;
const doc = win.document;
const nav = win.navigator;

// patchEnvironment(win, doc, nav, browserBaseline)
// win.eval("<same probe as browser>")
```

注意：

- `url` 必须设成目标 URL，会影响 `location`、`document.URL`、`document.domain`。
- `pretendToBeVisual: true` 可以让部分视觉时钟和 RAF 行为更接近浏览器。
- `resources: "usable"` 只在需要让 jsdom 加载外链资源时使用；若资源手动注入，保持更小闭环。
- 环境补丁必须在目标 SDK / JSVMP 加载前完成。
- 如果目标 SDK 加载时保存 `XMLHttpRequest.prototype.open`、`fetch` 或 DOM 方法引用，hook 和补丁必须更早安装。

建议产物：

```text
targets/<site>/samples/local-env-baseline.json
targets/<site>/samples/env-diff.json
targets/<site>/scripts/env/collect-local-env.js
targets/<site>/scripts/env/env-patch.js
targets/<site>/scripts/env/run.js
```

## 3. Diff 分级

不要见差异就补。先判断它是否“真实读取过、会影响输出、可局部补丁”。

| 等级 | 典型差异 | 处理策略 |
| --- | --- | --- |
| 致命 | native `toString` 暴露 jsdom / Node 实现 | 优先修 |
| 致命 | `navigator.plugins.length = 0` 或结构缺失 | 优先修 |
| 致命 | `navigator.webdriver` 异常 | 优先修 |
| 致命 | `document.hasFocus() = false` | 优先修 |
| 致命 | DOM layout 全 0 | 优先修 |
| 高危 | `Object.prototype.toString.call(document)` 标签不对 | 有读取证据时修 |
| 高危 | `Symbol.toStringTag` 错误或缺失 | 有读取证据时修 |
| 高危 | UA 家族与 `window.chrome` / `userAgentData` / native 格式不自洽 | 必须修自洽 |
| 高危 | `performance.timing/navigation/now/timeOrigin` 差异 | 时间参与签名时修 |
| 中危 | `Worker/Notification/AudioContext/fetch/matchMedia/indexedDB/caches/visualViewport` 存在性 | 被读取时修 |
| 低危 | 冷门 API、枚举顺序、与目标链路无关字段 | 记录，不补 |

优先使用 `trace_property_access`、`runtime-evidence.jsonl`、`env-read-trace.jsonl` 来判断真实读取项。没有 trace 时，再用 `compare_env` + first divergence 收敛。

## 4. 补丁原则与最小模板

补丁文件应写入当前目标工作区，例如：

```text
targets/<site>/scripts/env/env-patch.js
js_reverse_cache/env/ai-generated/<semantic-name>.js
```

不要写回 skill 自身目录。

### 4.1 native toString / markNative

这是 jsdom 环境伪装最容易失败的点。jsdom 的 DOM 方法大多是 JS 实现，`Function.prototype.toString` 会暴露源码。

硬规则：

- 全局 `Function.prototype.toString` 只统一接管一次。
- 不要“补强”第二次覆盖；二次覆盖常会暴露补丁函数自身源码。
- 需要 WeakSet 记录要伪装的函数。
- 需要源码模式兜底，识别 jsdom 内置方法漏网者。
- 需要匹配浏览器家族格式：Firefox native 多行，Chrome native 单行。
- 不要改 `Object.prototype`、`Array.prototype` 等基础原型。

最小骨架：

```javascript
function setupNativeToString(win, family) {
  const originalToString = win.Function.prototype.toString;
  const nativeSet = new WeakSet();

  function nativeSource(fn) {
    const name = fn && fn.name ? fn.name : "";
    if (family === "firefox") {
      return `function ${name}() {\n    [native code]\n}`;
    }
    return `function ${name}() { [native code] }`;
  }

  function markNative(fn) {
    if (typeof fn !== "function") return fn;
    nativeSet.add(fn);
    try {
      Object.defineProperty(fn, "toString", {
        value: function toString() { return nativeSource(fn); },
        configurable: true
      });
    } catch (_) {}
    return fn;
  }

  const jsdomPatterns = [
    /const\s+esValue\s*=/,
    /this\._globalObject/,
    /implSymbol/,
    /webidl\.conversions/,
    /HTMLConstructor/
  ];

  win.Function.prototype.toString = function toString() {
    if (nativeSet.has(this)) return nativeSource(this);
    let src = "";
    try { src = originalToString.call(this); } catch (_) {
      return family === "firefox"
        ? "function () {\n    [native code]\n}"
        : "function () { [native code] }";
    }
    if (jsdomPatterns.some((pattern) => pattern.test(src))) {
      return nativeSource(this);
    }
    return src;
  };

  markNative(win.Function.prototype.toString);
  return { markNative, nativeSet };
}
```

扫描建议：

- 扫描 `Document.prototype`、`HTMLDocument.prototype`、`Element.prototype`、`HTMLElement.prototype`、`Node.prototype`、`EventTarget.prototype`。
- 扫描 `XMLHttpRequest.prototype`、`HTMLCanvasElement.prototype`、`Storage.prototype`、`Location.prototype`、`URL.prototype`。
- 扫描时不要越过 `Object.prototype`。
- 扫描新增 stub 后再执行一次。

### 4.2 Symbol.toStringTag

硬规则：

- 优先设在正确 prototype 上，不要只设实例。
- `document` 目标常见期望是 `[object HTMLDocument]`。
- `screen` 期望 `[object Screen]`。
- `navigator` 期望 `[object Navigator]`。
- 不要通过改 `constructor.name` 当主要手段；这可能破坏继承和检测。

示例：

```javascript
function defineTag(obj, tag) {
  if (!obj || typeof Symbol === "undefined" || !Symbol.toStringTag) return;
  Object.defineProperty(obj, Symbol.toStringTag, {
    value: tag,
    configurable: true
  });
}

defineTag(win.HTMLDocument && win.HTMLDocument.prototype, "HTMLDocument");
defineTag(win.Document && win.Document.prototype, "HTMLDocument");
defineTag(win.Navigator && win.Navigator.prototype, "Navigator");
defineTag(win.Screen && win.Screen.prototype, "Screen");
defineTag(win.Window && win.Window.prototype, "Window");
```

### 4.3 navigator.plugins / mimeTypes

硬规则：

- 不要只把 `length` 设成非零。
- 需要 `PluginArray`、`Plugin`、`MimeType` 的外形、`item()`、`namedItem()`、迭代器和 `Symbol.toStringTag`。
- Chrome 分支常见 PDF 插件更多；Firefox 分支不要无证据伪造 Chrome 插件树。
- 以浏览器采集基准为准。

最小结构必须支持：

```javascript
navigator.plugins.length
navigator.plugins.item(0)
navigator.plugins.namedItem("PDF Viewer")
navigator.plugins[0].name
navigator.plugins[0].item(0)
navigator.mimeTypes.length
navigator.mimeTypes.item(0)
Object.prototype.toString.call(navigator.plugins)
```

### 4.4 navigator.webdriver 与基础字段

常见补丁：

- `navigator.webdriver`：与基准一致，通常为 `false`。
- `platform`、`language`、`languages`、`hardwareConcurrency`、`maxTouchPoints`、`cookieEnabled`、`pdfViewerEnabled`：按基准补。
- `userAgentData`：只在 Chrome/Chromium 分支或有读取证据时补。
- `connection` / `getBattery` / `deviceMemory`：只在读取或分支依赖时补。

不要在 Firefox UA 下默认补 `window.chrome` 和 `userAgentData`，除非目标脚本读取并接受这种混合外形。

### 4.5 document / performance

常见关键项：

- `document.hasFocus()`：活动页面基准通常为 `true`。
- `document.readyState`：目标运行阶段通常期望 `complete` 或至少非异常。
- `document.visibilityState`：通常为 `visible`。
- `document.hidden`：通常为 `false`。
- `performance.now()`、`performance.timeOrigin`、`performance.timing`、`performance.navigation`：时间参与签名时必须对齐。

注意：

- 不要让 `performance.now()` 每次返回固定值，很多签名依赖递增时间。
- 如果浏览器样本用固定输入验证，记录浏览器 `Date.now()`、`performance.now()`、输出时间戳精度。

### 4.6 DOM layout

jsdom 没有真实布局引擎，`offsetWidth/offsetHeight/getBoundingClientRect()` 常返回 0。若目标读取布局值，必须给出合理而稳定的值。

原则：

- 优先根据元素 inline style 解析宽高。
- 没有 style 时给稳定默认值。
- `getBoundingClientRect()` 返回对象要包含 `x/y/top/left/right/bottom/width/height`。
- 如果目标读取字体或真实渲染，jsdom 可能到达天花板，要评估 Canvas/font/GPU 或浏览器兜底。

### 4.7 Canvas / WebGL / Audio

原则：

- 不要输出大体积原始 canvas data。
- 优先记录 hash、长度、vendor、renderer、版本等摘要。
- Canvas 可用 `node-canvas` 或 `@napi-rs/canvas`，但引入依赖前先确认目标真的读取。
- WebGL 和 Audio 指纹如果直接参与哈希，简单 stub 很可能不够。
- 若浏览器输出能被协议请求接受，本地输出失败，应记录 first divergence。

### 4.8 Node.js 特征隐藏

只在目标上下文可见时处理：

- `process`
- `module`
- `exports`
- `require`
- `global`
- `Buffer`
- `__filename`
- `__dirname`

不要从 Node 外层污染目标上下文。隐藏失败时记录风险，不要破坏运行时本身。

## 5. 补丁加载顺序

推荐顺序：

```text
1. 创建 jsdom/vm 上下文
2. setupNativeToString / markNative
3. 扫描并标记内置原型链
4. navigator 基础字段、plugins、webdriver
5. document 状态、Symbol.toStringTag、performance
6. DOM layout、Canvas/WebGL/Audio 按需补
7. XHR/fetch hook 或 fake transport
8. SDK / JSVMP / 目标脚本
9. init/setup/cacheOpts/path 白名单
10. 触发导出函数或喂入请求
11. 捕获输出并验证
```

特别注意：

- 目标脚本可能在加载时保存原型引用，补丁必须早。
- 目标脚本可能覆盖 `URLSearchParams`、`fetch`、`XMLHttpRequest` 等 polyfill，捕获 hook 有时要晚于目标脚本。
- 如果是 SDK 拦截器，常见顺序是：环境补丁 -> fake XHR/fetch -> 目标 SDK -> 初始化 -> 触发请求 -> 捕获最终字段。

## 6. 沙箱内部验证

验证必须在目标看到的上下文里执行。

jsdom：

```javascript
const result = win.eval(`(() => {
  const d = document.createElement("div");
  d.style.cssText = "width:100px;height:80px";
  document.body.appendChild(d);
  const rect = d.getBoundingClientRect();
  const out = {
    createElementToString: document.createElement.toString(),
    pluginsLength: navigator.plugins && navigator.plugins.length,
    webdriver: navigator.webdriver,
    hasFocus: document.hasFocus(),
    docTag: Object.prototype.toString.call(document),
    screenTag: Object.prototype.toString.call(screen),
    rect: { width: rect.width, height: rect.height },
    ua: navigator.userAgent
  };
  d.remove();
  return out;
})()`);
```

最低检查：

| 检查 | 期望 |
| --- | --- |
| `document.createElement.toString()` | 与基准浏览器 native 外形一致 |
| `navigator.plugins.length` | 与基准一致，或至少非异常 |
| `navigator.webdriver` | 与基准一致 |
| `document.hasFocus()` | 与基准一致 |
| `Object.prototype.toString.call(document)` | 与基准一致 |
| DOM layout | 不再全部为 0 |
| UA 家族 | 与 native 外形、Chrome/Firefox 专项 API 自洽 |

## 7. 触发目标输出

### 导出函数

适合目标暴露 `sign()`、`generate()`、`encrypt()`、`window.xxx` 等入口。

要求：

- 固定输入。
- 浏览器端同输入输出样本。
- 沙箱端同输入输出样本。
- 比较长度、前缀、编码、字段顺序、时间戳精度。

### 喂入-截出

适合 JSVMP / SDK 劫持 XHR 或 fetch，在内部追加签名。

XHR 场景：

```text
安装 fake XMLHttpRequest
SDK 加载并保存 open/send/setRequestHeader 引用
调用 init/cacheOpts
在沙箱内发目标 URL
拦截最终 open URL、headers、body
```

fetch 场景：

```text
安装 fake fetch
SDK 加载并保存 fetch 引用
调用 init/cacheOpts
在沙箱内调用 fetch(targetUrl, init)
拦截最终 Request/url/headers/body
```

常见失败：

- XHR hook 只覆盖 `open`，但签名写在 `send` 或 `setRequestHeader`。
- 只测 XHR，实际业务走 fetch。
- 未传 `cacheOpts` / path 白名单，拦截器没有注册。
- hook 装太晚，SDK 保存了旧引用。
- hook 装太早，被目标 polyfill 覆盖。

### 完整初始化链路

适合多脚本 SDK：

```text
runtime/env patch
bootstrap script
vendor/runtime script
SDK glue script
init/setup/cacheOpts
trigger request
capture output
```

每个脚本 URL、版本、hash、加载顺序要写入 `samples/scripts.jsonl` 或 notes。

## 8. 服务端验收

不能只看本地输出。

成功标准：

- 固定输入下本地输出与浏览器输出格式对齐。
- 真实请求返回有效业务数据，不只是 HTTP 200。
- 同 session / 同 cookie / 同 UA / 同时间窗口内连续成功。
- 强时效字段至少连续 3 次成功；高风险 challenge 建议 5 次。
- 失败样本记录 first divergence。

失败解释：

| 现象 | 优先怀疑 |
| --- | --- |
| HTTP 200 + 空 body | 环境指纹不匹配或降级签名 |
| HTTP 200 + 字段少 | 风控态，不是成功态 |
| 浏览器签名可被 Node/Python 接受，本地签名不行 | 沙箱环境差异 |
| 浏览器签名也不被 Node/Python 接受 | TLS/HTTP 指纹、header、cookie、IP/账号绑定 |
| 间歇成功 | 时间戳、nonce、session 刷新、并发状态 |
| 入口输出稳定但服务端拒绝 | 请求拼装、编码、排序、cookie 或 header 契约 |

## 9. 证据记录格式

建议在 `samples/runtime-evidence.jsonl` 记录补丁来源：

```json
{"type":"env_read","path":"navigator.webdriver","source":"trace_property_access","request_id":"...","stack":"..."}
{"type":"env_diff","path":"document.hasFocus","browser":true,"local":false,"severity":"fatal"}
{"type":"patch","path":"document.hasFocus","file":"scripts/env/env-patch.js","reason":"fatal diff + read before signer"}
{"type":"verification","name":"browser-vs-local","input":"fixture-001","browser_len":128,"local_len":128,"status":"matched"}
```

补丁计划可写入 `scripts/env/patch-plan.md`：

```text
Patch: navigator.plugins
Evidence:
- samples/env-diff.json: plugins.length 5 vs 0
- samples/env-read-trace.jsonl: read before signer output
Scope:
- PluginArray/Plugin/MimeType minimal tree
Validation:
- win.eval Object.prototype.toString + item/namedItem
- fixture-001 signer output
Risk:
- Chrome/Firefox plugin shape mismatch remains possible
```

## 10. 红线

不要做：

1. 入口未知时直接补环境。
2. `success: true` 后不做 browser-vs-local 和服务端验收。
3. 全量补浏览器 API，不看读取证据。
4. 二次覆盖 `Function.prototype.toString`。
5. 修改 `Object.prototype`、`Array.prototype` 或基础原型。
6. 只设 `navigator.plugins.length`，不补对象树外形。
7. 只把 `Symbol.toStringTag` 设在实例上。
8. Firefox UA 下无证据补 Chrome-only API。
9. Chrome UA 下混入 Firefox-only API。
10. 把浏览器 cookie、sign、seed 硬编码成最终交付。
11. 把真实目标 JS、cookie、包样本写入 skill 目录。
12. HTTP 200 就当成功。

## 11. 与其它 reference 的关系

- 先读 `references/sandbox-fingerprint-validation.md`，确认是否进入沙箱指纹比对阶段。
- 本文负责 jsdom/vm/sdenv 深度环境伪装的具体执行。
- 需要模块树和加载顺序时读 `references/env-modules.md` 与 `references/loading-order.md`。
- 需要 native 外形、集中 runner、webpack module 运行时读 `references/env-core-advanced.md`。
- 需要最终 `sign.js`、HTTP 中间层和 Python 回放时读 `references/verification-and-replay.md`。
- Camoufox 证据文件和工具链统一遵循项目根目录 `skills-library/shared/camoufox-evidence-flow.md`。
