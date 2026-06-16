# Skill Router

本文件是 reverse-lab 的总控入口。它只负责路由、证据契约和维护规则，不承载长教程。

## 目标

1. 先判定任务类型，再选择最窄的 skill。
2. 先沉淀证据，再进入补环境、移植或协议交付。
3. 目标材料只写入 `targets/<site>/`、`js_reverse_cache/` 或 `cases/`，不写入 skill 目录。
4. Camoufox / CloakBrowser 采集到的是浏览器家族事实，不能混补。

## 路由表

| 用户目标 | 首选路线 | 不要走 |
| --- | --- | --- |
| 找 sign/token/header/cookie 的生成位置、脚本 URL、函数入口和调用链 | `find-crypto-entry` | 不要直接补环境或整包 AST |
| 只要一段 DevTools/Console/Snippets hook 脚本 | `browser-hook-snippets` | 不要展开完整入口定位 |
| 整文件混淆还原、字符串数组、控制流平坦化、Decode_action 风格 pass | `ast-deobfuscate` | 不要把入口未知问题当成解混淆问题 |
| 入口已知，目标 JS 需要在 Node.js/vm/jsdom/sdenv 中跑通 | `env-patch` | 不要在入口未知时补全浏览器宇宙 |
| 端到端恢复成脱离浏览器的 Python 采集器 | `web-protocol-recovery` | 不要把浏览器自动化当默认交付 |
| 瑞数/Ruishu/Rivers 固定项目骨架、首跳材料缓存、最小 runtime/proxy 观察 | `rs-reverse` | 不要在此 skill 深挖字节码或 URL suffix |
| WAF/JS challenge 动态 cookie 复现，且目标是可复用脚本 | `waf-cookie-pure-first` | 不要硬编码一次性浏览器 cookie |
| 滑块验证码协议链路、轨迹、厂商参数生成 | `captcha-slide-reverse` | 不要仅因有 JS 加密就走验证码 skill |
| 明确要 Python + iv8 + requests 紧凑脚本 | `iv8-web-reverse` 或更窄的 `adapters/*-iv8` | 不要转到不存在的外部 skill |

## Camoufox 证据层

Camoufox reverse MCP 是本项目的浏览器真值和运行时监控层，不是临时可选工具。涉及环境检测、补环境、JSVMP、cookie 来源、browser-vs-local 验证时，优先按这个链路记录证据：

```text
Camoufox browser truth
  -> runtime / env read trace
  -> local env baseline
  -> env diff
  -> patch plan
  -> patched local run
  -> browser-vs-local verification
  -> protocol replay verification
```

具体工具和产物契约见 `skills-library/shared/camoufox-evidence-flow.md`。

## Artifact Contract

每个目标放在 `targets/<source-name>/`：

```text
targets/<source-name>/
├── source/
├── scripts/
├── samples/
├── output/
└── notes.md
```

常用证据文件：

| 文件 | 作用 |
| --- | --- |
| `samples/task.json` | 任务元信息、阶段、成功标准和摘要 |
| `samples/network.jsonl` | 关键请求/响应、headers/body、状态和特征 |
| `samples/scripts.jsonl` | 关键脚本、入口、调用链、`source -> entry -> builder -> writer -> sink` |
| `samples/runtime-evidence.jsonl` | hook、断点、中间值、cookie/storage、first divergence |
| `samples/browser-env-camoufox.json` | Firefox/Gecko 家族浏览器基准 |
| `samples/browser-env-cloakbrowser.json` | Chrome/Chromium 家族浏览器基准 |
| `samples/local-env-baseline.json` | 本地 Node/vm/jsdom/sdenv 基准 |
| `samples/env-diff.json` | 浏览器与本地环境差异 |
| `samples/env-read-trace.jsonl` | 真实运行时读取了哪些环境属性 |
| `samples/verification.jsonl` | browser-vs-local 和协议回放验收记录 |
| `scripts/env/*` | 当前本地重建入口、补丁、polyfill 和固定上下文 |
| `output/*` | 验证后的可运行交付代码 |

`notes.md` 用中文记录结论和证据索引，不粘贴大段源码。

## Browser Tool Policy

1. Camoufox 是默认浏览器分析层，负责 Firefox/Gecko 基准、反检测、pre-inject、JSVMP trace、cookie/storage/network 观察和 browser-vs-local 验证。
2. CloakBrowser 是 Chrome/Chromium 对照层，只在目标明确依赖 Chrome 家族事实时使用。
3. Camoufox 与 CloakBrowser 样本必须分文件记录。不要把 Firefox native code 格式、`window.chrome`、`navigator.userAgentData`、`performance.memory` 混在同一个补丁假设里。
4. 浏览器自动化只是记录过的兜底交付路线，必须说明为什么纯协议、Node/vm/jsdom/sdenv、WASM helper、TLS/HTTP fingerprint 路线不能闭环。

## Handoff Rule

跨 skill 交接时，至少交代：

```yaml
stage: observe | capture | rebuild | patch | pure-port
currentSkill: <skill-name>
nextSkill: <skill-name>
targetRequest: <url/method/purpose>
knownFacts:
  - <已证事实>
missingFacts:
  - <仍缺证据>
artifacts:
  - <path>
reason: <为什么转交>
```

## Maintenance Rule

新增或重命名 skill 时必须同步：

1. `SKILL_ROUTER.md`
2. `catalog.yaml`
3. `skills-library/*/SKILL.md` 的 frontmatter 和跨 skill 路由
4. `evals/*` 中的 expected skill
5. `.agents/skills/` 和 `.codex/skills/` 中的 active 副本
6. `tools/list-skills.ps1` / `tools/audit-skills.ps1` 的输出假设

不要新增 `CLAUDE.md` 或 `.claude/skills` 维护链路。
