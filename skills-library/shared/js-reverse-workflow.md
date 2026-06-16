# JS Reverse Workflow

这是前端 JS 逆向任务的共享阶段协议。具体 skill 只保留本阶段相关操作，跨阶段交接遵循本文件。

## Stages

| Stage | 目标 | 典型 skill |
| --- | --- | --- |
| Observe | 确认目标请求、触发动作、保护家族、候选脚本 | `find-crypto-entry`, `web-protocol-recovery` |
| Capture | 捕获真实请求、入口、调用栈、运行时值、环境读取 | `find-crypto-entry`, `browser-hook-snippets` |
| Rebuild | 在本地重建最小可运行入口或协议链路 | `env-patch`, `ast-deobfuscate`, `web-protocol-recovery` |
| Patch | 按证据补环境、补状态、补传输包装 | `env-patch`, `web-protocol-recovery` |
| Pure / Port | 固化为纯协议、Python/Node/WASM helper 或 iv8 交付 | `web-protocol-recovery`, `waf-cookie-pure-first`, `iv8-web-reverse` |

## Gate

1. 入口未知，不进入补环境。
2. 只需要观察脚本，不展开完整入口定位。
3. 只要阅读版源码，优先 AST；但请求字段链路未知时先找入口。
4. 环境补丁必须来自 Camoufox/CloakBrowser/local diff 或 runtime trace。
5. 浏览器自动化不是默认最终交付。

## Handoff

交接至少包含：

```yaml
stage: observe | capture | rebuild | patch | pure-port
targetRequest: <url/method/purpose>
entry: <script/function/line or unknown>
evidence:
  - <path>
nextSkill: <skill-name>
reason: <why>
```

## Evidence

目标工作区优先使用：

- `samples/network.jsonl`
- `samples/scripts.jsonl`
- `samples/runtime-evidence.jsonl`
- `samples/env-read-trace.jsonl`
- `samples/env-diff.json`
- `samples/timeline.jsonl`
- `scripts/env/*`
- `output/fixtures.json`
