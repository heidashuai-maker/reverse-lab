# 案例：JSVMP + XHR 拦截器 + jsdom 环境伪装

> 难度：★★★★★
> 反爬类型：行为型 / 签名型混合
> 首选路线：`find-crypto-entry` -> `env-patch`
> 复现形态：jsdom 喂入-截出，必要时补浏览器环境指纹

## 适用范围

适用于安全 SDK 加载后改写 `XMLHttpRequest.prototype.open/send`，当业务 URL 命中路径规则时自动追加长签名参数的场景。算法主体在 JSVMP 中，静态还原成本高，优先让原始 SDK 在受控 jsdom 环境中运行，然后截获最终 URL 或 header。

## 技术指纹

- SDK glue 初始化函数负责注入路径列表。
- JSVMP 文件大，常见 UMD 导出、`_0x` 变量、while-switch、内部状态对象。
- 请求发出前，URL 末尾被追加一个 180 字符以上的长签名参数。
- 非真实浏览器环境可能生成格式正确但服务端拒绝的签名，例如返回空 body 或业务空数据。
- 环境检测常涉及 `Function.prototype.toString`、`navigator.webdriver`、plugins、DOM layout、canvas/WebGL/audio。

## 参数特征（快速路由）

| 参数 / 字段 | 位置 | 长度 / 字符集 | 生成时机 | 判定价值 |
| --- | --- | --- | --- | --- |
| `a_bogus` | URL query | 常见 180-192 字符，Base64 或自定义 Base64 变体 | XHR open/send 被 SDK 拦截后追加 | 高 |
| `X-Bogus` | URL query 或 header | 旧变体可能为较短字母数字串 | SDK 导出函数或拦截器生成 | 中 |
| `msToken` | Cookie / URL query | 常见 100+ 字符 token | 页面初始化或预热接口后出现 | 中 |
| `verifyFp` / `fp` | URL query / Cookie | `verify_...` 风格指纹 ID | 浏览器指纹初始化后出现 | 中 |
| 浏览器指纹 ID / 设备 ID | Cookie / storage / query | hex 或长 token | SDK 初始化阶段写入 | 中 |

高置信度组合：`a_bogus` 长签名 + 安全 SDK glue + XHR 拦截器 + 路径列表初始化。只看到 `msToken` 或 `fp` 不足以单独命中本 case，需要结合脚本特征或 XHR 改写证据。

## 指纹检测规则

```text
快速检测：
1. 搜索 SDK glue 初始化函数、路径列表、XHR open/send 改写。
2. 搜索长签名参数名，确认其由拦截器追加而不是业务代码手写。
3. 对 XHR open/send 做 hook，观察原始 URL 和最终 URL。
4. 用浏览器签名、本地 jsdom 签名分别回放，判断是否环境指纹参与。

高置信度：
- SDK 初始化后 XHR 被改写；
- 签名由拦截器追加；
- jsdom 生成签名格式正确但服务端拒绝。
```

## 已验证定位路径

```text
步骤 1：抓包定位带签名的业务请求。
步骤 2：保存 SDK 三件套或核心脚本到 targets/<site>/source/。
步骤 3：搜索路径注册逻辑，提取业务 path matcher。
步骤 4：在 jsdom 中按原加载顺序执行 SDK，并提前安装 XHR hook。
步骤 5：触发一次伪 XHR，截获追加后的签名参数。
步骤 6：如果服务端拒绝，采集 browser-vs-local 环境差异并最小补丁。
步骤 7：连续多次真实请求验收。
```

## Phase 处理流程

### Phase 1：网络捕获与请求定位

```text
1. 打开目标页面，不先假设算法。
2. 捕获业务请求，记录未签名前 URL、签名后 URL、Cookie、UA、Referer。
3. 搜索签名字段名，确认它是 URL 参数、header 还是 body 字段。
4. 保存关键请求到 targets/<site>/samples/network.jsonl。
```

### Phase 2：SDK 初始化链路

```text
1. 定位 SDK glue 初始化函数。
2. 提取 paths / enablePathList / route matcher。
3. 保存核心脚本到 targets/<site>/source/，不要每次远程下载。
4. 记录加载顺序：web page inline config -> glue -> monitor/sdk -> JSVMP。
```

### Phase 3：jsdom 喂入-截出

```text
1. 创建 jsdom。
2. 先安装我方 XHR hook。
3. 按真实顺序加载 SDK。
4. 调用初始化函数并传入 paths。
5. 触发伪 XHR，让 SDK 自己追加签名。
6. 从截获 URL 中取签名。
```

### Phase 4：环境差异闭环

```text
1. 浏览器签名可用，本地签名不可用 -> 进入环境指纹比对。
2. 分批采集 navigator / screen / document / performance / DOM layout / canvas。
3. 只补被证明读取且 browser-vs-local 不一致的点。
4. 每补一类，重新跑固定输入和真实请求。
```

### Phase 5：服务端验收

```text
1. 固定输入下签名长度、字符集、时间敏感性符合浏览器。
2. 连续多次请求返回完整业务数据。
3. HTTP 200 + 空 body 归为环境指纹失败，不归为算法成功。
```

## 链路图

```text
source: full URL query / cookie / UA / timestamp / SDK path config / browser env
entry: SDK glue init + JSVMP XHR interceptor
builder: JSVMP bytecode + env fingerprint collector + request matcher
writer: XHR open/send 期间追加 URL 签名参数
sink: XMLHttpRequest / protocol replay HTTP client
verification: browser signed URL == jsdom signed URL, replay returns full business data
```

## 加密 / 编码 / 签名方案

- 算法：JSVMP 内部自定义流程，默认不反编译字节码。
- 密钥来源：请求 URL、cookie、UA、时间、随机数、浏览器环境指纹和 SDK 状态。
- 输入字段：以 XHR hook 捕获的原始 URL 与最终 URL diff 为准。
- 输出字段：通常是 URL query 中的长签名参数。
- 还原策略：喂入原始 URL，让原始 SDK/JSVMP 在 jsdom 中执行，再截获最终签名 URL。

## 核心代码模板

### native toString 单次覆盖

```javascript
function installNativeToString(win) {
  const rawToString = win.Function.prototype.toString;
  const nativeFns = new WeakSet();

  function markNative(fn) {
    if (typeof fn === "function") nativeFns.add(fn);
    return fn;
  }

  const jsdomPatterns = [
    /const\s+esValue\s*=/,
    /this\._globalObject/,
    /tryImplForWrapper/,
    /ceReactionsPreSteps/,
  ];

  win.Function.prototype.toString = function patchedToString() {
    if (nativeFns.has(this)) {
      return `function ${this.name || ""}() { [native code] }`;
    }
    let src = "";
    try {
      src = rawToString.call(this);
    } catch {
      return "function () { [native code] }";
    }
    if (jsdomPatterns.some((pattern) => pattern.test(src))) {
      return `function ${this.name || ""}() { [native code] }`;
    }
    return src;
  };

  return { markNative };
}
```

### XHR 喂入-截出签名

```javascript
async function generateSignedUrl(dom, fullUrl, cookieStr) {
  const win = dom.window;
  const captured = [];

  if (cookieStr) {
    for (const part of cookieStr.split(";")) {
      win.document.cookie = part.trim();
    }
  }

  const rawOpen = win.XMLHttpRequest.prototype.open;
  win.XMLHttpRequest.prototype.open = function open(method, url, ...rest) {
    captured.push(String(url));
    return rawOpen.call(this, method, url, ...rest);
  };

  win.eval(`
    (function () {
      var xhr = new XMLHttpRequest();
      xhr.open("GET", ${JSON.stringify(fullUrl)}, true);
      xhr.send();
    })();
  `);

  await new Promise((resolve) => setTimeout(resolve, 500));
  return captured.find((url) => /[?&][^=&]+=[^&]{80,}/.test(url)) || null;
}
```

### 路径配置初始化占位

```javascript
function initSdkPaths(win, pathList) {
  if (typeof win.__SDK_INIT__ !== "function") {
    throw new Error("SDK init function not exported; locate glue init first");
  }
  win.__SDK_INIT__({
    paths: pathList,
  });
}
```

## 关键补丁方向

- `Function.prototype.toString`：只覆盖一次，用 WeakSet + jsdom 源码模式兜底。
- DOM 原型与 `Symbol.toStringTag`：不要乱改 `constructor.name`。
- `navigator.plugins` / `mimeTypes`：结构要像真实 PluginArray，而不只是 length。
- DOM layout：jsdom 默认 `offsetWidth/Height` 为 0，可能参与指纹。
- UA 自洽：Firefox UA 不补 Chrome-only API，Chrome UA 不补 Firefox-only API。

## 禁动清单与 UA 自洽

- 不要替换 `win.Error`，除非 trace 已证明目标读取 `Error.stack`。
- 不要修改任何 `constructor.name`；需要 `Object.prototype.toString` 时优先用 prototype 上的 `Symbol.toStringTag`。
- 不要改 `Object.prototype` / `Array.prototype` 这类全局原型。
- `Function.prototype.toString` 只允许覆盖一次，多层防御写在同一个函数体内。
- Firefox UA 下不要补 `navigator.userAgentData`、`window.chrome`、`performance.memory`、`navigator.connection` 等 Chrome-only API。
- Chrome UA 下不要补 `navigator.buildID`、`InstallTrigger` 等 Firefox-only API。

## 验证方法

- 签名格式验证：长度、字符集、参数名和浏览器样本一致。
- browser-vs-local 验证：固定 URL、cookie、UA 下，浏览器签名与 jsdom 签名一致或服务端等价接受。
- 环境补丁验证：每新增一类 env patch，先跑本地检测，再跑真实请求。
- 服务端验收：连续多次返回完整业务数据；`HTTP 200 + 空 body` 视为失败。
- 回退规则：补丁新增后签名仍失败，应回退未证实的环境 stub，而不是继续堆补丁。

## 踩坑记录

| # | 坑 | 现象 | 正确做法 |
| --- | --- | --- | --- |
| 1 | SDK 加载后才 hook XHR | 截不到最终签名 URL | 我方 hook 必须在 SDK 加载前安装 |
| 2 | 签名长度正确就认为成功 | 服务端返回空数据 | 做真实请求验收，检查环境指纹 |
| 3 | env patch 越补越多 | 输出不稳定、泄露新特征 | 先 trace 证明读取，再最小补丁 |
| 4 | 混用 Chrome/Firefox 指纹 | 签名被静默拒绝 | 按目标 UA 分支单独维护补丁 |

## 可验证事实清单

- [ ] XHR 拦截器安装点已定位。
- [ ] 路径注册规则已提取。
- [ ] 同一固定输入下 browser-vs-local 签名一致或协议验收通过。
- [ ] 环境补丁只覆盖被证明读取的属性/方法。
