# 案例：RS6 Cookie + 412 Challenge + sdenv

> 难度：★★★★★
> 反爬类型：签名型 Cookie challenge
> 首选路线：`rs-reverse`，缺少该 skill 时按 `find-crypto-entry` 采证后转 `env-patch`
> 复现形态：sdenv / 魔改 jsdom / 真实执行挑战 JS 生成客户端 Cookie

## 适用范围

适用于首跳返回 HTTP 412 挑战页，服务端下发一个 Cookie，客户端执行混淆 JS 后再生成另一个 Cookie，随后携带完整 Cookie 组重新请求才放行的场景。

不适用于普通 403、普通验证码、单纯 HTTP header 缺失导致的失败。

## 技术指纹

- 首次请求返回 HTTP 412，响应体是精简 HTML challenge。
- HTML 内含 `<meta id="固定ID" content="动态token" r="m">`、`$_ts` 全局配置、外部混淆 JS 和动态入口函数调用。
- `$_ts` 通常包含 `nsd` 数字种子和 `cd` 长配置串，挑战 JS 中可见 `if($_ts.cd){...}` 之类入口判断。
- Set-Cookie 同时下发会话 Cookie 与服务端 `XxxYyyZzz2AaaaS` 类 Cookie。
- 客户端 JS 执行后生成同 basename 的 `XxxYyyZzz2AaaaT` 类 Cookie，最终请求需要会话 Cookie + `S` Cookie + `T` Cookie。
- 混淆 JS 可能检测 `document.all` 的浏览器特殊行为，普通 jsdom 会卡死或分支错误。

## 参数特征（快速路由）

| 参数 / 字段 | 位置 | 长度 / 字符集 | 生成时机 | 判定价值 |
| --- | --- | --- | --- | --- |
| `XxxYyyZzz2AaaaS` | Set-Cookie / Cookie | basename + `S` 后缀；basename 中常见 `2` 分隔；服务端下发，常为长生命周期 | 首跳 412 响应头下发 | 高 |
| `XxxYyyZzz2AaaaT` | Cookie | 与 `S` Cookie 同 basename + `T` 后缀；客户端 JS 生成 | 挑战 JS 执行后写入 | 高 |
| `acw_tc` | Set-Cookie / Cookie | 服务端会话标识 | 首跳 412 或挑战响应时下发 | 中 |
| `<meta ... content="动态token" r="m">` | HTML meta content | content 常见几十到百余字符，每次挑战变化 | 412 challenge HTML 内嵌 | 高 |
| `$_ts.nsd` / `$_ts.cd` | inline script | `nsd` 数字种子；`cd` 长配置串 | 412 challenge HTML 内嵌 | 高 |
| `_$xx()` 动态入口函数 | HTML inline script | `_$` + 2-3 位左右随机名，入口名每次可能变化 | 412 challenge HTML 底部调用 | 高 |

高置信度组合：HTTP 412 + 同 basename 的 `XxxYyyZzz2AaaaS/T` Cookie 对 + `$_ts.nsd/cd` + 动态 `_$xx()` 入口。单独看到 `acw_tc` 不足以判定 RS6，需要结合 412 body 结构。

## 指纹检测规则

```text
快速检测：
1. 不加 hook 首次请求，确认是否 412 challenge。
2. 读取 412 HTML，搜索动态配置、meta token、入口函数调用。
3. 检查 Set-Cookie 是否含 `XxxYyyZzz2AaaaS`，再对比成功请求 Cookie 是否多出同 basename 的 `XxxYyyZzz2AaaaT`。
4. 用真实浏览器验证 Cookie 组可放行，再评估 sdenv/沙箱路线。

高置信度：
- 412 + `$_ts.nsd/cd` + 动态 `_$xx()` 入口 + 同 basename 的服务端 S Cookie 与客户端 T Cookie 同时存在。
```

## 已验证定位路径

```text
步骤 1：用浏览器抓首跳 412、外部 JS、成功 200 请求。
步骤 2：保存 412 HTML、Set-Cookie、挑战 JS 到 targets/<site>/。
步骤 3：对比失败请求和成功请求 Cookie 头，确认客户端生成字段。
步骤 4：验证普通 jsdom 是否因 document.all / 环境检测失败。
步骤 5：采用 sdenv 或等价运行时真实执行挑战页。
步骤 6：从 cookie jar 取完整 Cookie 组，用协议请求回放验收。
```

## Phase 处理流程

### Phase 1：确认 412 challenge 结构

```text
1. 首次请求不要带浏览器自动修复逻辑，记录原始 412。
2. 保存响应体、Set-Cookie、外部 JS URL、入口函数名。
3. 判断响应体是否包含 meta token、全局动态配置、入口调用。
```

### Phase 2：拆 Cookie 来源

```text
1. 从 412 Set-Cookie 中提取会话 Cookie 和 `XxxYyyZzz2AaaaS`。
2. 从成功请求 Cookie header 中找同 basename 的 `XxxYyyZzz2AaaaT`。
3. `S` 来自服务端 Set-Cookie，`T` 通常来自客户端挑战 JS 生成。
4. 写入 samples/runtime-evidence.jsonl：server cookie / client cookie 分开记录。
```

### Phase 3：验证环境难点

```text
1. 尝试普通 jsdom 执行挑战页。
2. 如果卡死、无 Cookie、死循环，检查 document.all、Function.toString、navigator 等环境检测。
3. document.all 特殊行为无法用普通 JS 完整模拟时，转 sdenv 或真实浏览器兜底。
```

### Phase 4：sdenv 执行挑战页

```text
1. 用同一 UA 请求 challenge 页面。
2. 等待挑战 JS 执行结束。
3. 从 cookie jar 取完整 Cookie 组。
4. 用同一 UA/header 分支请求目标页面或 API。
```

### Phase 5：协议回放验收

```text
1. 成功请求必须携带会话 Cookie + S Cookie + T Cookie。
2. Referer、Sec-Fetch-*、Host、Accept、UA 尽量与生成 Cookie 阶段一致。
3. Cookie 有效但仍失败时，再看 TLS/HTTP 指纹、IP/会话绑定。
```

## 链路图

```text
source: 412 HTML meta token / $_ts.nsd / $_ts.cd / Set-Cookie S / UA / env
entry: dynamic _$xx() entry in challenge HTML
builder: RS6 challenge JS + browser env collector + cookie packet encoder
writer: cookie jar writes XxxYyyZzz2AaaaT
sink: follow-up document/API request with acw_tc + S Cookie + T Cookie
verification: protocol replay returns 200 business response instead of 412 challenge
```

## 加密 / Cookie 方案

- 算法：挑战 JS 内部生成客户端 Cookie，加密细节不作为优先还原目标。
- 密钥来源：`$_ts.nsd/cd`、动态 meta token、服务端 `S` Cookie、浏览器环境和时间随机数。
- 输入字段：412 HTML 动态配置、Set-Cookie、UA、浏览器环境。
- 输出字段：同 basename 的 `XxxYyyZzz2AaaaT` Cookie。
- 还原策略：用 sdenv 或等价运行时真实执行挑战 JS，读取 cookie jar 后协议回放。

## 核心代码模板

### sdenv Cookie 客户端骨架

```javascript
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

const https = require("https");
const { jsdomFromUrl } = require("sdenv");

class ChallengeCookieClient {
  constructor({ origin, entryPath, userAgent }) {
    this.origin = origin.replace(/\/+$/, "");
    this.entryPath = entryPath;
    this.userAgent = userAgent;
    this.dom = null;
    this.cookie = "";
  }

  async init() {
    const url = `${this.origin}${this.entryPath}`;
    this.dom = await jsdomFromUrl(url, {
      userAgent: this.userAgent,
      consoleConfig: { error() {} },
    });

    await new Promise((resolve) => {
      this.dom.window.addEventListener("sdenv:exit", resolve);
      setTimeout(resolve, 8000);
    });

    this.cookie = this.dom.cookieJar.getCookieStringSync(this.origin);
    if (!this.cookie) throw new Error("challenge did not produce cookies");
    return this;
  }

  request(path) {
    const target = new URL(path, this.origin);
    return new Promise((resolve, reject) => {
      const req = https.request(
        {
          hostname: target.hostname,
          path: `${target.pathname}${target.search}`,
          method: "GET",
          headers: {
            "User-Agent": this.userAgent,
            Cookie: this.cookie,
            Referer: `${this.origin}/`,
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
          },
        },
        (res) => {
          let body = "";
          res.on("data", (chunk) => (body += chunk));
          res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body }));
        },
      );
      req.on("error", reject);
      req.end();
    });
  }

  close() {
    if (this.dom) this.dom.window.close();
  }
}
```

### 412 HTML 结构提取

```javascript
function parseChallengeHtml(html) {
  return {
    hasTsConfig: /\$_ts\s*=|if\s*\(\s*\$_ts\.cd\s*\)/.test(html),
    tsFields: {
      hasNsd: /\bnsd\b/.test(html),
      hasCd: /\bcd\b/.test(html),
    },
    metaTokens: [...html.matchAll(/<meta[^>]+content=["']([^"']+)["'][^>]*\br=["']m["']/g)].map((m) => m[1]),
    scriptUrls: [...html.matchAll(/<script[^>]+src=["']([^"']+)["']/g)].map((m) => m[1]),
    entryCalls: [...html.matchAll(/(_\$[A-Za-z0-9]+)\s*\(\s*\)/g)].map((m) => m[1]),
  };
}
```

## 关键经验

- 412 不是结论，必须看响应体结构和 Set-Cookie；`XxxYyyZzz2AaaaS/T` 同 basename 成对出现才是本 case 的高价值指纹。
- Cookie 有效但请求失败时，检查 UA、Referer、Fetch Metadata、Host、TLS/HTTP 指纹是否与生成 Cookie 时一致。
- 这类挑战通常不适合手写全量算法；让原始挑战 JS 在合适运行时执行更稳。
- `document.all` 的 `typeof === "undefined"` 是浏览器特殊行为，纯 JS 很难完整模拟。

## 验证方法

- 首跳验证：无 Cookie 或缺 T Cookie 时稳定返回 412 challenge。
- Cookie 来源验证：`S` 只来自 Set-Cookie，`T` 只在挑战 JS 执行后出现。
- sdenv 验证：cookie jar 中能拿到会话 Cookie + `S` + `T`。
- Header 自洽验证：生成 Cookie 的 UA 与回放 UA 一致，Referer 和 Fetch Metadata 不缺失。
- 协议回放验证：携带完整 Cookie 组后返回目标业务响应，而不是再次 412。

## 变体说明

| 变体 | 差异点 | 调整策略 |
| --- | --- | --- |
| RS4/RS5 | JS 体积和环境检测项少于 RS6 | 可先尝试普通 jsdom 或最小补环境 |
| Cookie-only | 只需要 Cookie 即可访问 | sdenv 生成 Cookie 后直接协议回放 |
| Cookie + URL suffix | 除 Cookie 外还需要 URL 后缀签名 | 本 case 只覆盖 Cookie，后缀签名需另建 case |
| HTTPS 证书链异常 | 本地请求 TLS 校验失败 | 记录证书问题，必要时设置测试用 TLS 策略 |
| API 二次签名 | Cookie 放行后 API 仍有业务 sign | Cookie challenge 与业务 sign 分两条链路记录 |

## 踩坑记录

| # | 坑 | 现象 | 正确做法 |
| --- | --- | --- | --- |
| 1 | 只看状态码猜厂商 | 路线走偏 | 读取 412 body 和 Set-Cookie 结构 |
| 2 | 普通 jsdom 执行挑战 JS | 卡死或不写 Cookie | 使用 sdenv 或真实浏览器基准验证 |
| 3 | Cookie 生成 UA 与请求 UA 不一致 | Cookie 有但 400/412 | UA/header/TLS 与生成阶段保持一致 |
| 4 | 固定入口函数名 | 下一次请求失效 | 入口函数名按模式匹配，不写死 |

## 可验证事实清单

- [ ] 412 challenge HTML 已保存并脱敏记录结构。
- [ ] 同 basename 的 `XxxYyyZzz2AaaaS/T` Cookie 对已确认，且来源已区分。
- [ ] `$_ts.nsd/cd`、动态 meta token、`_$xx()` 入口已确认。
- [ ] 挑战 JS 执行后的 cookie jar 能拿到完整 Cookie 组。
- [ ] 协议回放使用同一 UA/header 分支并通过验收。
