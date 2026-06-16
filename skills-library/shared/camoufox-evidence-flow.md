# Camoufox Evidence Flow

本文是 Camoufox reverse MCP 的共享证据流程。它用于环境分析、环境补充、运行时监控和补丁后验证。

## 角色

| 角色 | 代表工具 | 产物 |
| --- | --- | --- |
| MCP 自检 | `check_environment` | `samples/tool-check-camoufox.json` |
| 浏览器真值 | `compare_env`, `evaluate_js`, `cookies`, `get_storage`, `export_state` | `samples/browser-env-camoufox.json`, `samples/browser-state-camoufox.json` |
| 网络证据 | `network_capture`, `list_network_requests`, `get_network_request`, `get_request_initiator` | `samples/network.jsonl`, `samples/request-initiators.jsonl` |
| 运行时 hook | `inject_hook_preset`, `hook_function`, `hook_jsvmp_interpreter` | `samples/runtime-evidence.jsonl` |
| JSVMP 源码级插桩 | `instrumentation(action="install|reload|log|status|stop")` | `samples/jsvmp-instrumentation.jsonl` |
| 引擎级环境读取 | `launch_browser(enable_trace=true)`, `trace_property_access` | `samples/env-read-trace.jsonl` |
| 离线签名验证 | `verify_signer_offline` | `samples/signature-verification.jsonl` |

## 标准流程

1. 启动前执行 `check_environment`，记录工具版本、依赖和残留状态。
2. 导航前按目标选择是否 pre-inject：
   - XHR/fetch/cookie 观察：`navigate(pre_inject_hooks=["xhr","fetch","cookie"])`
   - JSVMP 低侵入观察：先 `hook_jsvmp_interpreter(mode="transparent", persistent=true)` 再导航
   - 源码级插桩：先 `instrumentation(action="install", url_pattern=...)` 再导航
3. 采集浏览器基准：
   - 通用环境：`compare_env()`
   - 定点值：`evaluate_js("(() => { ...; return data })()")`
   - cookie/storage：`cookies(action="get")`, `get_storage(storage_type="local|session")`
4. 本地运行 Node/vm/jsdom/sdenv，保存 `samples/local-env-baseline.json` 和运行输出。
5. 生成 `samples/env-diff.json`，按“真实读取过、会影响输出、可局部补丁”排序。
6. 每个环境补丁都要能追溯到一条 trace/diff 证据。
7. 补丁后再次运行本地固定输入，和浏览器输出做 browser-vs-local 验证。
8. 最后才做协议回放验证，并写入 `samples/verification.jsonl`。

## Cookie 来源

当前不要依赖单独的 `analyze_cookie_sources` 作为确定能力。使用组合证据：

1. `network_capture(action="start", capture_body=true)`
2. `inject_hook_preset(preset="cookie", persistent=true)`
3. 触发目标请求或刷新
4. `list_network_requests` + `get_network_request(include_headers=true)`
5. `cookies(action="get")`
6. 对比请求前、响应后、JS 写入日志和最终 cookie jar

结论只允许写成以下几类之一：

| writer | 证据 |
| --- | --- |
| `http-set-cookie` | 响应 headers 出现 `Set-Cookie` 且 cookie jar 随后变化 |
| `document-cookie` | cookie hook 捕获 JS 写入 |
| `redirect-or-wrapper` | redirect chain / wrapper 页面之后出现 |
| `challenge-js` | 返回的 challenge JS 执行后写入或触发 Set-Cookie |
| `unknown` | 证据不足，继续采集 |

## 环境补丁规则

1. 优先补真实读取过的属性，不按“浏览器大全”批量补。
2. Camoufox 样本代表 Firefox/Gecko 家族事实；CloakBrowser 样本代表 Chrome/Chromium 家族事实。
3. 每个补丁记录来源：

```json
{
  "patch": "navigator.webdriver",
  "reason": "trace_property_access saw navigator.webdriver before signer output",
  "browser_value": false,
  "local_value": "undefined",
  "source": "samples/env-read-trace.jsonl + samples/env-diff.json"
}
```

4. 强环境检测场景下，优先 `trace_property_access` 或源码级 `instrumentation`，少用会改变对象形态的全局 Proxy。
5. `hook_jsvmp_interpreter(mode="proxy")` 可被签名型反爬检测；瑞数/Akamai 类优先 `mode="transparent"` 或源码级插桩。

## 验证门槛

补环境任务不能只以“脚本不报错”为完成。最低完成标准：

1. 入口、固定输入、浏览器输出和本地输出都有样本。
2. 已记录浏览器基准、本地基准和差异。
3. 每个保留补丁都有证据来源。
4. 固定输入下本地输出与浏览器输出一致，或记录 first divergence。
5. 协议回放至少成功两次，或明确剩余风险。
