# MCP Hook 工具层

本文用于把浏览器 hook 需求映射到可用工具。默认仍能输出 DevTools Console / Snippets 脚本，但当 Camoufox MCP 可用时，应优先使用它完成前置注入、运行时探针和 Cookie 归因。

## 工具优先级

1. Camoufox MCP：首选。适合 Firefox/Gecko 指纹基准、首屏挑战、强反检测、Cookie 来源归因、JSVMP 轻量探针。
2. CloakBrowser MCP：可选。适合 Chrome/Chromium 指纹基准、Playwright MCP 兼容自动化、Chrome-only 分支对照。
3. DevTools / 普通浏览器 MCP：兜底。适合无强检测页面、临时 Console/Snippets 注入。

如果当前会话没有暴露 Camoufox 或 CloakBrowser 工具，仍输出普通 JS hook，但要说明缺少的能力，例如无法保证首屏 pre-inject、无法自动 Cookie 归因、无法稳定采集反检测指纹。

## Camoufox MCP 推荐能力

| 需求 | 推荐能力 | 说明 |
| --- | --- | --- |
| 首屏挑战页 hook | `navigate(pre_inject_hooks=[...], via_blank=true)` | hook 先于 challenge JS 生效 |
| 普通 XHR/fetch 观察 | `inject_hook_preset("xhr")` / `inject_hook_preset("fetch")` | 默认持久化，跨导航重注入 |
| Cookie 写入来源 | `inject_hook_preset("cookie")` + `analyze_cookie_sources` | 区分 JS `document.cookie` 和 HTTP `Set-Cookie` |
| 广谱低开销观察 | `inject_hook_preset("runtime_probe")` + `get_runtime_probe_log` | 优先于全局 Proxy |
| 指定函数参数/返回值 | `hook_function(mode="trace")` | 不暂停页面，采样调用栈 |
| 防止页面覆盖 hook | `hook_function(mode="intercept", non_overridable=true)` | 用于关键原型方法 |
| JSVMP 环境读取 | `hook_jsvmp_interpreter(mode="transparent")` | 签名型反爬优先低侵入 |
| 深度 VMP 读写 | `instrumentation(action="install")` | 只在轻量 hook 不足时启用 |

## Cookie Hook 注意点

普通 `Object.defineProperty(document, "cookie", ...)` 不可靠，因为真实 getter/setter 通常在 `Document.prototype` 或 `HTMLDocument.prototype` 上。普通脚本需要沿原型链找 descriptor：

```javascript
function findCookieDescriptor() {
  let proto = Object.getPrototypeOf(document);
  while (proto) {
    const descriptor = Object.getOwnPropertyDescriptor(proto, "cookie");
    if (descriptor) return { owner: proto, descriptor };
    proto = Object.getPrototypeOf(proto);
  }
  return null;
}
```

如果使用 Camoufox MCP，优先直接使用 cookie preset 和 `analyze_cookie_sources`，因为 HTTP `Set-Cookie` 不会经过 `document.cookie` setter。

## 注入时机

| 场景 | 注入时机 |
| --- | --- |
| 首屏挑战、WAF 二跳、Akamai/RS challenge | pre-inject 后再导航 |
| 普通页面已加载，想临时看调用 | `evaluate_js` / Console 注入 |
| SDK 会在加载时保存原型引用 | hook 必须早于目标 SDK 加载 |
| 目标 SDK 会覆盖 polyfill | 捕获 hook 可能要晚于目标 JS 注入 |
| 需要复测 hook 是否生效 | 注入后重载，并确认日志或 hook 列表 |

## 降噪规则

1. 高频 hook 默认按 URL、字段名、调用次数过滤。
2. Cookie、token、Authorization 默认脱敏或截断。
3. request/response body 默认只记录类型、长度、片段。
4. Canvas/WebGL/Audio 默认记录调用点和摘要，不输出完整大对象。
5. 只有用户明确要求完整值，才提供 `FULL_LOG = true` 开关。

## 与补环境的交接

如果 hook 发现目标读取了环境属性，应把证据写入 `runtime-evidence.jsonl` 或等价文件，至少包含：

```json
{
  "type": "env_read",
  "path": "navigator.webdriver",
  "value_preview": "false",
  "stack": "...",
  "request_id": "...",
  "evidence": "runtime_probe/camoufox"
}
```

后续交给 `env-patch` 时，应同时提供浏览器基准、读取路径、触发请求和 first divergence。
