# reverse-lab

Web/JS 逆向专题工作台，用于管理项目级 skills、目标站点材料、运行时证据、补环境脚本和协议恢复交付物。

## 入口

- 总控路由：`SKILL_ROUTER.md`
- 项目规则：`AGENTS.md`
- Skill 源库：`skills-library/`
- 默认激活层：`.codex/skills/`、`.agents/skills/`

不要新增 `CLAUDE.md` 或 `.claude/skills` 维护链路。

## 目录

```text
.agents/              通用 Agent 项目级激活 skill
.codex/skills/        Codex 项目级激活 skill
skills-library/       完整 skill 库，默认不全部启用
skills-library/shared/跨 skill 共享协议、Camoufox 证据流等公共资料
js_reverse_cache/     临时下载、抓包、运行时缓存和一次性调试输出
targets/              按目标沉淀源码、样本、脚本、输出和 notes
cases/                可复用、已验证、已脱敏的案例沉淀
templates/            target notes 和复现 runner 模板
tools/                skill 管理和审计脚本
tmp/                  外部参考项目和一次性实验材料
```

`tmp/` 不视为正式沉淀，skill 不应直接依赖其中的文件。

## Skill 使用原则

1. 先看 `SKILL_ROUTER.md` 判定任务类型。
2. 默认只启用核心通用 skill。
3. WAF、captcha、adapters 等窄场景 skill 按需启用。
4. 目标材料不写入 skill 目录。
5. 修改 skill 后同步 active 副本并跑审计。

默认核心 skill：

```text
web-protocol-recovery
find-crypto-entry
browser-hook-snippets
ast-deobfuscate
env-patch
```

## Camoufox 证据流

Camoufox reverse MCP 是浏览器真值、运行时监控和补环境验证层。涉及环境检测、JSVMP、cookie 来源、browser-vs-local 验证时，按 `skills-library/shared/camoufox-evidence-flow.md` 记录证据。

常见产物：

```text
targets/<site>/samples/browser-env-camoufox.json
targets/<site>/samples/browser-env-cloakbrowser.json
targets/<site>/samples/local-env-baseline.json
targets/<site>/samples/env-diff.json
targets/<site>/samples/env-read-trace.jsonl
targets/<site>/samples/runtime-evidence.jsonl
targets/<site>/samples/verification.jsonl
```

Camoufox 样本代表 Firefox/Gecko 家族事实；CloakBrowser 样本代表 Chrome/Chromium 家族事实。补环境时不要混用。

## Target 规范

每个逆向目标使用一个目录：

```text
targets/<source-name>/
├── source/       原始 JS、HTML、WASM、字体、页面源码等
├── scripts/      解混淆、补环境、协议验证、辅助分析脚本
├── samples/      请求/响应样本、证据 JSONL、cookie/header、环境基准
├── output/       最终可运行程序、交付脚本、稳定复现代码
└── notes.md      中文分析记录
```

`notes.md` 应记录目标信息、防护判断、逆向路线、关键值来源、计算过程、证据索引、验证结论和剩余风险。源码放 `scripts/` 或 `output/`，不要大段粘进 notes。

## 常用命令

列出 skill：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\list-skills.ps1
```

启用 skill：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\enable-skill.ps1 -Name jd-h5st-iv8
```

只启用到 Codex：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\enable-skill.ps1 -Name jd-h5st-iv8 -Targets codex
```

停用 skill：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\disable-skill.ps1 -Name jd-h5st-iv8 -Targets codex,agents
```

审计 skill：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\audit-skills.ps1
```

创建 target：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name xhs-homefeed
```

创建带 runner 的 target：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-python -Runner python-protocol
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-node -Runner node-protocol
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-vm -Runner vm-sandbox
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-wasm -Runner wasm-helper
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-browser -Runner browser-auto-fallback
```
