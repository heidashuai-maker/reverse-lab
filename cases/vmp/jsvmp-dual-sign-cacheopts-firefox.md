# 案例：JSVMP 双签名 + cacheOpts + Firefox 指纹

> 难度：★★★★★
> 反爬类型：行为型 / 双通道签名
> 首选路线：`find-crypto-entry` -> `env-patch`
> 复现形态：jsdom 喂入-截出 + Firefox/Gecko 指纹自洽

## 适用范围

适用于新版安全 SDK 同时改写 XHR 和 fetch：一个签名追加到 URL 参数，另一个签名写入 header；业务路径是否触发由 `cacheOpts` 或类似配置注册。若浏览器基准来自 Firefox/Gecko，`Function.prototype.toString` 的 native code 格式、Firefox-only 属性也必须自洽。

## 技术指纹

- 初始化配置中出现 `cacheOpts`、paths、ttl 或类似路径缓存策略。
- XHR 与 fetch 都被 SDK 改写。
- URL 参数和请求 header 同时出现动态签名。
- 环境检测比单签名更敏感，可能检查 Firefox native code 字符串格式、`navigator.buildID`、CSS2Properties 等。

## 参数特征（快速路由）

| 参数 / 字段 | 位置 | 长度 / 字符集 | 生成时机 | 判定价值 |
| --- | --- | --- | --- | --- |
| `X-Bogus` | URL query | 常见 180-192 字符，Base64 或自定义 Base64 变体 | XHR 通道命中路径规则后追加 | 高 |
| `X-Gnarly` | request header | 常见 120-140 字符，自定义编码 | fetch 通道或导出签名函数生成 | 高 |
| `msToken` | Cookie / URL query | 常见 100+ 字符 token | 页面初始化、预热或 Cookie 写入后出现 | 中 |
| `verifyFp` / `fp` | URL query / Cookie | `verify_...` 风格指纹 ID | 浏览器指纹初始化后出现 | 中 |
| `cacheOpts.paths` | inline config / boot config | path matcher 数组 | SDK glue 初始化时注册 | 高 |

高置信度组合：`X-Bogus` 和 `X-Gnarly` 同时存在，且 `cacheOpts` 参与路径注册。只有 `X-Bogus` 没有 header 签名时，优先回看单签名 JSVMP case。

## 指纹检测规则

```text
快速检测：
1. 搜索 cacheOpts / paths / ttl，确认路径注册来源。
2. hook XMLHttpRequest.prototype.open 和 window.fetch。
3. 触发业务请求，确认 URL 参数和 header 同时变化。
4. 采集浏览器基准；若使用 Camoufox，按 Firefox/Gecko 分支补环境。

高置信度：
- cacheOpts 存在；
- XHR/fetch 双通道都参与；
- 缺少任一签名都会被服务端拒绝。
```

## 已验证定位路径

```text
步骤 1：抓包记录完整业务请求，标注 URL 签名和 header 签名。
步骤 2：定位 SDK 初始化配置，复制 paths/cacheOpts 到本地沙箱。
步骤 3：按真实顺序加载 SDK，并提前安装 XHR/fetch hook。
步骤 4：触发 XHR 获取 URL 签名，触发 fetch 获取 header 签名。
步骤 5：若服务端拒绝，做 Firefox/Gecko 环境差异比对。
步骤 6：使用与浏览器分支一致的 HTTP/TLS 客户端回放。
```

## Phase 处理流程

### Phase 1：确认双签名

```text
1. 抓业务请求，分别标注 URL 参数签名和 header 签名。
2. 删除 URL 签名重放一次，删除 header 签名重放一次。
3. 两者任一缺失都失败，才进入双通道路线。
```

### Phase 2：还原初始化配置

```text
1. 搜索 cacheOpts、paths、ttl、route matcher。
2. 从 inline config 或 boot config 中提取完整路径配置。
3. 本地沙箱必须传同一份配置，否则拦截器可能不触发。
```

### Phase 3：双通道截获

```text
1. XHR hook 负责截获 URL 参数签名。
2. fetch hook 负责截获 header 签名。
3. 两个 hook 都要在 SDK 加载前安装。
```

### Phase 4：Firefox/Gecko 指纹自洽

```text
1. 若浏览器基准来自 Camoufox，按 Firefox 分支补环境。
2. native code toString 使用 Firefox 多行格式。
3. 不补 window.chrome、navigator.userAgentData、performance.memory 等 Chrome-only API。
```

### Phase 5：请求回放

```text
1. 带完整 URL 签名 + header 签名 + Cookie 回放。
2. 若浏览器签名可用、本地请求失败，单独验证 TLS/HTTP 指纹。
```

## 链路图

```text
source: full URL query / cookie / UA / timestamp / cacheOpts paths / Firefox env
entry: SDK glue init + XHR interceptor + fetch interceptor
builder: JSVMP bytecode + route matcher + frontier/header sign function
writer: XHR writes URL signature, fetch writes header signature
sink: XMLHttpRequest / fetch / protocol replay HTTP client
verification: URL signature + header signature both present, replay returns full business data
```

## 加密 / 编码 / 签名方案

- 算法：JSVMP 内部自定义双签名，默认采用喂入-截出。
- 密钥来源：请求 URL、cookie、UA、时间、浏览器环境指纹、SDK 初始化配置和 cacheOpts path matcher。
- 输入字段：URL 签名读取完整 query；header 签名读取 fetch/header 上下文和 SDK 状态。
- 输出字段：一个写入 URL query，一个写入 request header。
- 还原策略：同一沙箱内同时触发 XHR 和 fetch，截获两个通道的输出。

## 核心代码模板

### Firefox native code 格式

```javascript
function installFirefoxNativeToString(win) {
  const rawToString = win.Function.prototype.toString;
  const nativeFns = new WeakSet();

  function markNative(fn) {
    if (typeof fn === "function") nativeFns.add(fn);
    return fn;
  }

  function asFirefoxNative(fn) {
    return `function ${fn && fn.name ? fn.name : ""}() {\n    [native code]\n}`;
  }

  win.Function.prototype.toString = function patchedToString() {
    if (nativeFns.has(this)) return asFirefoxNative(this);
    let src = "";
    try {
      src = rawToString.call(this);
    } catch {
      return "function () {\n    [native code]\n}";
    }
    if (/const\s+esValue\s*=|this\._globalObject|tryImplForWrapper/.test(src)) {
      return asFirefoxNative(this);
    }
    return src;
  };

  return { markNative };
}
```

### cacheOpts 初始化骨架

```javascript
function initWithCacheOpts(win, cachePaths) {
  const config = {
    cacheOpts: {
      paths: cachePaths,
      ttl: 300,
    },
  };

  const resources = {
    monitor: { paths: cachePaths },
  };

  if (typeof win.__SDK_GLUE_INIT__ !== "function") {
    throw new Error("replace __SDK_GLUE_INIT__ with the real glue init function");
  }
  win.__SDK_GLUE_INIT__(config, resources);
}
```

### URL 签名 + header 签名双截获

```javascript
async function generateDualSign(dom, fullUrl, cookieStr) {
  const win = dom.window;
  const capturedUrls = [];
  const capturedHeaders = [];

  if (cookieStr) {
    for (const part of cookieStr.split(";")) {
      win.document.cookie = part.trim();
    }
  }

  const rawOpen = win.XMLHttpRequest.prototype.open;
  win.XMLHttpRequest.prototype.open = function open(method, url, ...rest) {
    capturedUrls.push(String(url));
    return rawOpen.call(this, method, url, ...rest);
  };

  const rawFetch = win.fetch;
  win.fetch = function fetch(url, opts = {}) {
    capturedHeaders.push(opts.headers || {});
    return rawFetch.call(this, url, opts);
  };

  win.eval(`
    var xhr = new XMLHttpRequest();
    xhr.open("GET", ${JSON.stringify(fullUrl)}, true);
    xhr.send();
    fetch(${JSON.stringify(fullUrl)}, { headers: {} }).catch(function(){});
  `);

  await new Promise((resolve) => setTimeout(resolve, 500));
  return {
    signedUrl: capturedUrls.find((url) => /[?&][^=&]+=[^&]{40,}/.test(url)) || null,
    signedHeaders: capturedHeaders.find((headers) => Object.keys(headers).length) || null,
  };
}
```

## 核心经验

- 双签名意味着双通道：只 hook XHR 会漏 header，只 hook fetch 会漏 URL 参数。
- `cacheOpts` 是新版路径注册关键；只传旧版 paths 可能导致拦截器不触发。
- Firefox/Gecko 基准下，native code 字符串通常是多行格式；Chrome 单行格式会暴露不自洽。
- TLS/HTTP 指纹可能是最后一关，浏览器签名可用但 Node/Python 请求失败时要单独验证。

## 禁动清单与 UA 自洽

- `cacheOpts` 必须从页面初始化配置提取完整结构，不要只凭路径前缀手写一小段。
- Firefox/Gecko 基准下，native `toString` 使用多行格式：`function name() {\n    [native code]\n}`。
- Firefox UA 下不要补 `window.chrome`、`navigator.userAgentData`、`performance.memory`。
- 不要只验证其中一个签名；URL 签名和 header 签名必须同时参与真实请求验收。
- 浏览器签名可用但本地 HTTP 失败时，优先拆分验证 TLS/HTTP 指纹，而不是继续改签名算法。

## 验证方法

- 双通道验证：分别确认 URL query 中的签名和 request header 中的签名都被写入。
- 缺失项验证：去掉任一签名重放应失败，确认不是冗余字段。
- cacheOpts 验证：换 path 后拦截器触发行为与浏览器一致。
- Firefox 环境验证：native `toString`、`navigator.buildID`、CSS2Properties 等分支与基准一致。
- 协议回放验证：完整 URL 签名 + header 签名 + Cookie 一起回放通过。

## 踩坑记录

| # | 坑 | 现象 | 正确做法 |
| --- | --- | --- | --- |
| 1 | 漏传 cacheOpts | SDK 加载正常但业务路径不签名 | 从页面初始化脚本提取完整配置 |
| 2 | 只截获 URL 签名 | 请求仍被拒 | 同时截获 header 签名 |
| 3 | Firefox 基准却补 Chrome toString | 签名格式对但验收失败 | native code 格式与 UA/浏览器基准一致 |
| 4 | 忽略 TLS 指纹 | 浏览器签名可用，本地请求失败 | 使用匹配浏览器分支的 HTTP/TLS 客户端 |

## 可验证事实清单

- [ ] cacheOpts 或等价路径注册配置已提取。
- [ ] URL 签名和 header 签名的生成通道已分别定位。
- [ ] Firefox/Chrome 环境基准没有混用。
- [ ] 真实协议回放同时携带两个签名并通过验收。
