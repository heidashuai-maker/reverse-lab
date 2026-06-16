# Camoufox Bridge For iv8

使用 Camoufox 采集 iv8 复现所需真值：

1. `check_environment` 确认 MCP 状态。
2. `network_capture(action="start", capture_body=true)` 开启网络证据。
3. `navigate(..., pre_inject_hooks=["xhr","fetch","cookie"])` 或先装 `hook_jsvmp_interpreter(mode="transparent")` 再导航。
4. `list_network_requests` 找目标请求。
5. `get_network_request(include_headers=true, include_body=true)` 保存 headers/body。
6. `get_request_initiator` 保存调用栈。
7. `compare_env` / `trace_property_access` 保存浏览器环境和真实读取路径。
8. `cookies(action="get")`、`get_storage` 保存会话状态。

这些证据用于决定 iv8 需要哪些输入和 bridge，不用于盲目复制浏览器自动化。
