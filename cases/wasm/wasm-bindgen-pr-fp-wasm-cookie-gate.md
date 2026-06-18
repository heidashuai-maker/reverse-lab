# 案例：wasm-bindgen 双 Cookie Gate（pr_fp + wasm）

> 难度：★★★★☆
> 反爬类型：WASM 指纹 Cookie / JS challenge / 外层 WAF 混合
> 首选路线：`web-protocol-recovery`，必要时先用 `find-crypto-entry` 定位 WASM 入口
> 复现形态：Node.js + 原始 wasm-bindgen glue + 最小浏览器环境；真实 Chrome/CDP 只作真值校验
> 最后验证日期：2026-06-17

## 适用范围

适用于页面预热阶段通过两个 WASM 组件生成放行 Cookie 的场景：一个指纹组件生成 `pr_fp`，另一个 wasm-bindgen 组件生成 `wasm`。业务请求需要同时携带这两个 Cookie，缺失、版本不匹配或出口被外层 WAF 拦截时，会进入 451/挑战页。

不适用于只有普通 JS challenge、只有服务端 Set-Cookie、或业务参数签名与 Cookie gate 无关的场景。只看到 Cookie 名 `wasm` 也不够，需要结合 wasm-bindgen glue、`main()` 入口和 `document.cookie` sink 一起判断。

## 技术指纹

### JS / WASM / 资源特征

- [x] 存在两组资源：`fp.js` + `fp_bg.wasm`，以及 `wasm.js` + `wasm_bg.wasm`。
- [x] 第二组资源路径常见形态为 `/Wasm/api/v1/wasm.js` 和 `/Wasm/api/v1/wasm_bg.wasm`，查询串可能带时间戳或版本号。
- [x] glue 中有典型 wasm-bindgen 结构：`__wbindgen_*`、`__widl_*`、对象堆数组、`WebAssembly.instantiate` / `instantiateStreaming`。
- [x] export 包含 `memory`、`main`、`__wbindgen_start`；本次验证版本中 `main` 与 `__wbindgen_start` 指向同一核心函数。
- [x] import 中存在 Cookie 写入 sink：`__wbg_setcookie_<hash>`，本次验证版本为 `__wbg_setcookie_b04b7af29c82f976`。
- [x] WASM 静态字符串包含环境探测标签：`PHANTOM_UA`、`PHANTOM_PROPERTIES`、`PHANTOM_ETSL`、`PHANTOM_LANGUAGE`、`PHANTOM_WEBSOCKET`、`PHANTOM_OVERFLOW`、`PHANTOM_WINDOW_HEIGHT`、`HEADCHR_UA`、`WEBDRIVER`、`HEADCHR_CHROME_OBJ`、`HEADCHR_PERMISSIONS`、`HEADCHR_IFRAME`、`SELENIUM_DRIVER`、`CHR_BATTERY`、`SEQUENTUM`。

### 参数与请求特征

- [x] 业务请求前 Cookie 中出现 `pr_fp` 和 `wasm`。
- [x] `pr_fp` 是 64 位 hex，来自指纹 WASM 组件。
- [x] `wasm` 是 32 位 hex，来自 wasm-bindgen 组件执行 `main()` 后写入。
- [x] `wasm` Cookie 常带短有效期，本次样本中模板字符串包含 `wasm=; max-age=; domain=; path=/; samesite=none; secure`，实测有效期约数分钟级。
- [x] 外层响应可能带 `Server: ddos-guard` 与 `__ddg*` Cookie；这只说明还有 WAF 外层，不等于本 case 的两个 Cookie 已正确生成。

## 参数特征（快速路由）

| 参数 / 字段 | 位置 | 长度 / 字符集 | 生成时机 | 判定价值 |
| --- | --- | --- | --- | --- |
| `pr_fp` | Cookie | 64 位 hex，小写 `[0-9a-f]` | `fp.js` 初始化并调用 `fp.get()` 后写入 | 高 |
| `wasm` | Cookie | 32 位 hex，小写 `[0-9a-f]` | `wasm.js` 初始化 `wasm_bg.wasm` 后调用 `wasm.main()` 写入 | 高 |
| `__wbg_setcookie_<hash>` | wasm-bindgen import | import 函数名，hash 后缀随构建可能变化 | WASM import table 构造阶段 | 高 |
| `main` / `__wbindgen_start` | WASM export | export 函数名 | glue 初始化后暴露，调用后触发 Cookie 写入 | 高 |
| `__ddg1_` / `__ddg8_` / `__ddg9_` / `__ddg10_` | Set-Cookie / Cookie | 外层 WAF 会话字段 | WAF 放行或挑战阶段 | 中 |

高置信度组合：`pr_fp` 64 hex + `wasm` 32 hex + `fp_bg.wasm` + `wasm_bg.wasm` + `wasm.main()` + `__wbg_setcookie_<hash>`。单独看到 `wasm` Cookie 或 `Server: ddos-guard` 不足以命中本 case。

## 指纹检测规则

```text
快速检测：
1. 在网络面板搜索 .wasm，确认是否有指纹 WASM 与 gate WASM 两组资源。
2. 搜索 glue JS：WebAssembly.instantiate、__wbindgen、__widl、__wbg_setcookie。
3. Hook document.cookie setter，观察 pr_fp 与 wasm 分别由哪个脚本写入。
4. 调用顺序复现：fp.default(fp_bg.wasm) -> fp.get() -> wasm.default(wasm_bg.wasm) -> wasm.main()。
5. 用生成出的 Cookie 直接回放业务页，确认返回业务 HTML/API，而不是 451、DDoS-Guard 或 challenge。

高置信度：
- Cookie 名、长度、字符集与本 case 一致；
- wasm-bindgen glue 中存在 main() 与 setcookie import；
- 本地调用原始 WASM 资源生成的 wasm 与真实浏览器同版输出一致；
- 携带 pr_fp + wasm 后协议回放能拿到业务响应。

排除条件：
- Cookie 只由服务端 Set-Cookie 下发；
- JS 中没有 WASM 资源和 wasm-bindgen glue；
- 只有外层 __ddg* Cookie，未出现 pr_fp/wasm 双 Cookie。
```

## 已验证定位路径

```text
步骤 1：抓首页和业务页，保存 fp.js/fp_bg.wasm/wasm.js/wasm_bg.wasm。
步骤 2：用 Cookie setter hook 确认 pr_fp 与 wasm 的写入脚本。
步骤 3：静态分析 wasm.js，定位 default loader、main wrapper、__wbg_setcookie_<hash>。
步骤 4：解析 wasm_bg.wasm imports/exports，确认 main、__wbindgen_start、memory、setcookie sink。
步骤 5：在真实 Chrome/CDP 中执行同样的资源加载顺序，作为 browser truth。
步骤 6：在 Node.js 中补最小 window/document/navigator/screen/canvas/WebGL/UAParser 环境，直接运行原始 glue + WASM。
步骤 7：对比 browser-vs-local 的 wasm 输出；版本一致时，wasm 应完全一致。
步骤 8：用本地生成的 pr_fp + wasm 做协议回放，返回业务页才算验收。
```

## Phase 处理流程

### Phase 1：资源与版本确认

```text
目标：确认本次失败是不是资源版本、Cookie 缺失还是出口/WAF 问题。
输入：页面 HTML、网络请求、fp/wasm 资源、业务页响应。
操作：
1. 保存 fp.js、fp_bg.wasm、wasm.js、wasm_bg.wasm。
2. 记录每个资源的 SHA256 和字节数。
3. 业务失败时同时保存 451/challenge 响应和成功业务响应样本。
产物：source hashes、headers、失败/成功 HTML 分类。
成功判定：能明确当前线上资源版本；后续本地生成必须使用同版资源。
```

### Phase 2：入口与写入点定位

```text
目标：找到真正写 Cookie 的入口，而不是只停在脚本 URL。
输入：fp.js、wasm.js、浏览器 cookie hook 记录。
操作：
1. 搜索 fp.default / fp.get，确认 pr_fp 写入链。
2. 搜索 wasm.default / wasm.main，确认 wasm 写入入口。
3. 搜索 __wbg_setcookie_<hash>，确认 document.cookie sink。
4. 解析 wasm_bg.wasm export，记录 main、__wbindgen_start、memory。
产物：source -> entry -> writer 映射。
成功判定：能用固定调用顺序触发两次 Cookie 写入。
```

### Phase 3：最小环境重建

```text
目标：脱离完整浏览器，直接运行原始 WASM helper。
输入：同版 fp/wasm 资源、UA、location、document.cookie jar、浏览器环境基线。
操作：
1. 在 Node.js 中安装 window/document/navigator/screen/location/canvas/WebGL 等最小对象。
2. 安装 Function.prototype.toString native-like 伪装。
3. 提供 document.cookie getter/setter，把写入结果收集到 cookie jar。
4. 先运行 fp.default + fp.get，再运行 wasm.default + wasm.main。
产物：pr_fp、wasm、cookieHeader。
成功判定：能稳定得到 64 hex 的 pr_fp 与 32 hex 的 wasm。
```

### Phase 4：browser-vs-local 对齐

```text
目标：证明本地生成不是“格式正确但不可用”。
输入：真实 Chrome/CDP 输出、本地 Node 输出、当前资源哈希。
操作：
1. 真实 Chrome 通过同一出口生成 pr_fp/wasm 并回放业务页。
2. 本地 Node 使用线上当前资源生成 pr_fp/wasm。
3. 对比 wasm 输出；本 case 中 wasm 与资源版本强绑定，同版应一致。
4. 如果 pr_fp 不一致但回放通过，记录它是可接受的环境指纹差异。
产物：browser truth、local output、差异解释。
成功判定：本地生成的 Cookie 组可以直接用于协议回放。
```

### Phase 5：协议回放验收

```text
目标：确认最终交付不依赖浏览器自动化。
输入：本地生成的 pr_fp + wasm、同一 UA、业务页 URL 或 API。
操作：
1. 携带 Cookie header、UA、Accept、Referer 发真实业务请求。
2. 分类响应：business_html / business_json / blocked_451 / challenge / unknown。
3. 业务页 HTML 需命中稳定 DOM 标记或业务字段。
4. 如果返回 451，先检查出口、外层 WAF、资源版本，再怀疑算法。
产物：协议回放响应、headers、分类结果。
成功判定：返回 HTTP 200 且命中业务 DOM/API 字段。
```

## 链路图

```text
source:
  fp.js + fp_bg.wasm
  wasm.js + wasm_bg.wasm
  UA / location.hostname / navigator / screen / canvas / WebGL / plugins / mimeTypes
entry:
  fp.default(fp_bg.wasm) -> fp.get()
  wasm.default(wasm_bg.wasm) -> wasm.main()
builder:
  wasm-bindgen object heap + WASM imports + environment probes + regex/domain logic
writer:
  document.cookie setter via __wbg_setcookie_<hash>
sink:
  Cookie header: pr_fp=<64hex>; wasm=<32hex>
verification:
  browser truth Cookie generation
  local Node helper generation
  protocol replay returns business response instead of 451/challenge
```

## 加密 / Cookie 方案

- 算法：不优先移植 WASM 内部算法，优先复用原始 wasm-bindgen glue + WASM bytes。
- 输入字段：UA、location、navigator、screen、canvas、WebGL、plugins、mimeTypes、permissions、iframe、Function.toString 等环境事实。
- 输出字段：`pr_fp` 与 `wasm` 两个 Cookie。
- 会话绑定：`wasm` 与当前 `wasm.js/wasm_bg.wasm` 版本强绑定；资源换版后旧 `wasm` 会稳定失效。
- 环境绑定：`pr_fp` 可随环境变化而不同；只要与当前出口、UA、WAF 状态兼容，未必需要与浏览器逐字一致。

## 核心代码模板

### Node.js 直接运行原始 wasm-bindgen 资源

```javascript
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function makeCookieJar() {
  const jar = new Map();
  return {
    set(rawCookie) {
      const first = String(rawCookie).split(";")[0];
      const index = first.indexOf("=");
      if (index < 0) return;
      jar.set(first.slice(0, index).trim(), first.slice(index + 1).trim());
    },
    get(name) {
      return jar.get(name);
    },
    header() {
      return [...jar].map(([k, v]) => `${k}=${v}`).join("; ");
    },
  };
}

function installMinimalBrowserEnv({ origin, ua, cookieJar }) {
  const url = new URL(origin);

  global.window = global;
  global.self = global;
  global.location = {
    href: origin + "/",
    protocol: url.protocol,
    hostname: url.hostname,
  };
  global.navigator = {
    userAgent: ua,
    platform: "Win32",
    language: "ru-RU",
    languages: ["ru-RU", "ru", "en-US", "en"],
    webdriver: false,
    plugins: { length: 5, item: () => null },
    mimeTypes: { length: 2, item: () => null },
    permissions: { query: async () => ({ state: "prompt" }) },
    mediaDevices: { enumerateDevices: async () => [] },
  };
  global.screen = { width: 1365, height: 900, availWidth: 1365, availHeight: 860, colorDepth: 24, pixelDepth: 24 };
  global.document = {
    get cookie() {
      return cookieJar.header();
    },
    set cookie(value) {
      cookieJar.set(value);
    },
    createElement(tag) {
      return makeElement(tag);
    },
    getElementById() {
      return null;
    },
    body: makeElement("body"),
    documentElement: makeElement("html"),
  };
}

function makeElement(tagName) {
  return {
    tagName: String(tagName).toUpperCase(),
    style: {},
    children: [],
    appendChild(node) { this.children.push(node); return node; },
    removeChild(node) { this.children = this.children.filter((item) => item !== node); return node; },
    setAttribute() {},
    getAttribute() { return null; },
    hasAttribute() { return false; },
    getContext() { return makeCanvasContext(); },
    canPlayType() { return "probably"; },
    clientWidth: 128,
    clientHeight: 64,
  };
}

function makeCanvasContext() {
  return {
    drawImage() {},
    getImageData() { return { data: new Uint8ClampedArray([255, 102, 0, 255]) }; },
    getParameter() { return "WebKit WebGL"; },
    getExtension() { return {}; },
    getSupportedExtensions() { return []; },
  };
}

async function runCookieGate(sourceDir) {
  const cookieJar = makeCookieJar();
  installMinimalBrowserEnv({
    origin: "https://example.test",
    ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    cookieJar,
  });

  vm.runInThisContext(fs.readFileSync(path.join(sourceDir, "fp.js"), "utf8"));
  await global.fp.default(fs.readFileSync(path.join(sourceDir, "fp_bg.wasm")));
  await global.fp.get();

  vm.runInThisContext(fs.readFileSync(path.join(sourceDir, "wasm.js"), "utf8"));
  await global.wasm.default(fs.readFileSync(path.join(sourceDir, "wasm_bg.wasm")));
  global.wasm.main();

  return {
    pr_fp: cookieJar.get("pr_fp"),
    wasm: cookieJar.get("wasm"),
    cookieHeader: cookieJar.header(),
  };
}
```

### 回放验收骨架

```python
import requests

def replay(url, ua, pr_fp, wasm, proxy=None):
    session = requests.Session()
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})
    response = session.get(
        url,
        headers={
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": url,
            "Cookie": f"pr_fp={pr_fp}; wasm={wasm}",
        },
        timeout=45,
    )
    text = response.text or ""
    if response.status_code == 451 or "blocked" in text.lower():
        return "blocked_451", response
    if "业务页稳定 DOM 标记" in text:
        return "business_html", response
    if "challenge" in text.lower():
        return "challenge", response
    return "unknown", response
```

## 关键经验

- `wasm` 不是随便一个 32 位 hex；它必须与当前 `wasm.js/wasm_bg.wasm` 版本匹配。资源换版后，旧 helper 会稳定产出旧值，格式正确但服务端拒绝。
- `fp.js/fp_bg.wasm` 与 `wasm.js/wasm_bg.wasm` 要分开看：前者产 `pr_fp`，后者产 `wasm`，不能只验证其中一个。
- 外层 WAF 出口会干扰判断。同一 Cookie 组在坏出口可能 451，在可用出口可返回业务页；失败时先确认代理/出口。
- 本地 `pr_fp` 和浏览器 `pr_fp` 可以不同；只要协议回放通过，不要为了逐字一致过度补环境。
- `main` 与 `__wbindgen_start` 指向同一核心函数时，glue 初始化后再次调用 `main()` 会触发写 Cookie；不要只停在 `default()`。

## 验证方法

- 本地函数级验证：运行原始 `fp.js/fp_bg.wasm` 和 `wasm.js/wasm_bg.wasm`，检查 `pr_fp` 为 64 hex、`wasm` 为 32 hex。
- browser-vs-local 验证：真实 Chrome/CDP 生成 `wasm` 后，本地使用同版 WASM 资源应生成相同 `wasm`。
- 资源版本验证：记录 `wasm.js` 与 `wasm_bg.wasm` 的 SHA256；同名同大小不代表同版，哈希必须一致。
- 协议回放验证：携带本地生成的 `pr_fp` + `wasm`、同一 UA 和 Referer 请求业务页，返回 HTTP 200 且命中业务 DOM 标记。
- 失败判定：HTTP 451、DDoS-Guard/challenge 页面、业务 DOM 缺失都不能算成功。

## 本次验证事实（脱敏）

- 真实 Chrome/CDP 通过本地 `7890` 出口生成 `pr_fp=<64hex>` 与 `wasm=<32hex>` 后，业务页返回 `HTTP 200`。
- 本地 Node helper 使用线上当前资源后生成同版 `wasm=<32hex>`，协议回放返回 `HTTP 200`，HTML 命中 `b-case-header` 与 `js-case-header-case_num`。
- 当前验证版 `wasm.js` SHA256：`629506b643500d4650b9795ff4e8f0c71cd53d78c55c119e26a5abe68bbe514f`。
- 当前验证版 `wasm_bg.wasm` SHA256：`bb0c1d4f8f88ef177cf5c66a6d974a9609a45503d60eb94d4d4264a12998f660`。
- 同日旧本地资源仍为相同字节数但不同哈希，生成旧 `wasm` 后业务回放为 451；这是资源版本漂移，不是代码骨架失效。
- 当前验证版 `fp.js/fp_bg.wasm` 哈希未变化，差异集中在 `wasm.js/wasm_bg.wasm`。

## 踩坑记录

| # | 坑 | 现象 | 正确做法 |
| --- | --- | --- | --- |
| 1 | 只看文件大小判断资源未变 | `wasm.js/wasm_bg.wasm` 大小相同但哈希变了，本地仍产旧 `wasm` | 每次验收前拉取当前资源并记录 SHA256 |
| 2 | 旧 `wasm` 格式正确但不可用 | Cookie 是 32 hex，却回放 451 | 用同版浏览器输出或当前资源重新生成 |
| 3 | 把外层 451 误判成算法失败 | 代理不可用或出口被 WAF 拦截时，浏览器也无法通过 | 分离“Cookie 算法验证”和“出口/WAF 验证” |
| 4 | 只运行 `default()` | WASM 初始化成功但没有写 `wasm` Cookie | 初始化后显式调用 `wasm.main()` |
| 5 | 过度追求 `pr_fp` 与浏览器完全一致 | 本地 `pr_fp` 与浏览器不同但请求可通过 | 以协议回放为最终验收，不把非必要环境差异扩大化 |

## 变体说明

| 变体 | 差异点 | 调整策略 |
| --- | --- | --- |
| Cookie 名变化 | `pr_fp` 或 `wasm` 改名 | 以 `document.cookie` sink 和长度/字符集重新确认，不硬编码名称 |
| Emscripten glue | 出现 `Module.cwrap` / `ccall` | 转读 WASM playbook，按 cwrap 入口恢复 |
| Worker 内 WASM | 主线程只看到 `postMessage` | hook Worker 构造、URL.createObjectURL、postMessage |
| 外层 WAF 强绑定出口 | Cookie 正确仍 451 | 保持生成 Cookie 和回放请求使用同一出口、UA、会话策略 |
| 响应/API 二次签名 | Cookie 放行后还有业务 sign | 将 Cookie gate 与业务 sign 分两条 case 链路记录 |

## 可验证事实清单

- [ ] 网络中存在 `fp.js/fp_bg.wasm` 与 `wasm.js/wasm_bg.wasm` 两组资源。
- [ ] `pr_fp` 是客户端生成的 64 位 hex Cookie。
- [ ] `wasm` 是客户端生成的 32 位 hex Cookie。
- [ ] `wasm.js` 中存在 wasm-bindgen glue、`default()` loader、`main()` wrapper。
- [ ] `wasm_bg.wasm` import 中存在 `__wbg_setcookie_<hash>`。
- [ ] `wasm_bg.wasm` export 中存在 `memory`、`main`、`__wbindgen_start`。
- [ ] 使用当前同版资源，本地 Node helper 能生成 `pr_fp` 和 `wasm`。
- [ ] 使用本地生成的 `pr_fp + wasm`，协议回放返回业务响应而不是 451/challenge。
- [ ] 资源换版时旧 `wasm` 会失效，必须重新拉取并更新哈希。

## 脱敏检查

- [x] 未写入真实域名和完整业务 URL。
- [x] 未写入完整真实 Cookie 值，只保留 Cookie 名、长度、字符集、短前缀形态和哈希证据。
- [x] 未粘贴大段目标 JS/WASM/HTML。
- [x] 保留了可复用的参数特征、入口函数、sink 函数、Phase 流程和验证方法。
