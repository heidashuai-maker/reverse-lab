# reverse-lab

逆向专题工作台。这个项目用于集中管理 Web/JS 逆向相关 skill、目标站点材料、复现脚本和分析记录。

## 目录说明

```text
.agents/              通用 Agent 项目级配置，当前用于启用项目级 skill
.codex/skills/        Codex 项目级启用 skill
.claude/skills/       Claude Code 项目级启用 skill
.playwright-mcp/      Playwright MCP 调试运行痕迹，保存页面快照和 console 日志
skills-library/       完整 skill 库，默认不全部启用
js_reverse_cache/     临时下载的 JS/HTML/WASM/字体/抓包样本
targets/              按目标站点沉淀的源码、请求样本、复现脚本
cases/                可复用案例和交付结果
tools/                skill 管理和审查脚本
templates/            target notes 和复现 runner 模板
tmp/                  临时外部参考项目、实验材料和一次性中间文件
```

### Agent 配置目录

`.agents/`、`.codex/`、`.claude/` 都是项目级 Agent 配置目录，用来让不同客户端在进入本项目时加载同一批核心 skill。它们不是样本目录，也不应该写入目标站点 JS、HTML、WASM、cookie、headers 或抓包材料。

- `.agents/skills/`：通用 Agent 激活层，当前和 Codex/Claude 启用同一批核心 skill。
- `.codex/skills/`：Codex 使用的项目级 skill 激活层。
- `.claude/skills/`：Claude Code 使用的项目级 skill 激活层。
- `skills-library/`：完整 skill 源库，是维护 skill 的主位置；项目级激活目录只放需要常驻启用的副本。

`.playwright-mcp/` 是浏览器调试工具产生的运行痕迹目录，当前包含 `console-*.log` 和 `page-*.yml`。这些文件用于临时回看页面状态、控制台输出和调试现场，不属于 skill，也不作为长期案例沉淀。需要长期保存的目标材料应整理到 `targets/<site>/samples/` 或 `targets/<site>/source/`。

### 缓存与案例目录

`js_reverse_cache/`、`cases/` 分别对应不同生命周期的材料：

- `js_reverse_cache/`：临时调查缓存区。用于放浏览器自动化 profile、临时下载的 JS/HTML/WASM/字体、抓包中间物、一次性调试输出等。这里的内容默认可再生成，不应作为唯一证据来源；有复用价值的材料要整理进对应的 `targets/<site>/source/`、`samples/` 或 `scripts/`。
- `cases/`：可复用案例沉淀区。用于放已经验证过、可迁移参考的案例总结、稳定复现片段、交付样例或通用分析结果。它和 `targets/` 的区别是：`targets/` 面向某个正在或曾经分析的具体目标，`cases/` 面向后续可复用的经验沉淀。
- `tmp/`：临时工作区。用于拉取外部参考项目、放一次性实验材料或迁移对照文件。这里的内容不视为本项目正式沉淀，不应被 skill 直接依赖。

### 工具脚本目录

`tools/` 保存项目维护脚本，主要用于管理 skill 激活状态和初始化 target 工作区。这里不放目标站点源码、抓包样本或逆向输出。

- `tools/list-skills.ps1`：扫描 `skills-library/` 下所有 `SKILL.md`，列出 skill 分组、名称、路径，以及是否已启用到 `.agents/skills/`、`.codex/skills/` 和 `.claude/skills/`。
- `tools/enable-skill.ps1`：把 `skills-library/` 中指定 skill 复制到项目级激活目录。默认同时启用到 Agent、Codex 和 Claude，可用 `-Targets codex` 等方式控制单个目标；已有目录时默认跳过，带 `-Replace` 才覆盖。
- `tools/disable-skill.ps1`：从 `.agents/skills/`、`.codex/skills/` 或 `.claude/skills/` 删除指定已启用 skill，不删除 `skills-library/` 中的源库版本。
- `tools/audit-skills.ps1`：审查 `skills-library/`、`.agents/skills/`、`.codex/skills/`、`.claude/skills/` 中的 `SKILL.md`，检查 frontmatter、`name`、`description` 和目录名是否一致。
- `tools/new-target.ps1`：创建新的 `targets/<source-name>/` 目录，并初始化 `source/`、`scripts/`、`samples/`、`output/` 和 `notes.md`；可用 `-Runner` 复制项目级代码骨架。

### 模板目录

`templates/` 保存项目级模板，不保存真实目标材料。

- `templates/target-notes-template.md`：新建 target 时使用的中文分析记录模板。
- `templates/runners/`：按复现形态整理的落地模板索引，包括纯 Python、纯 Node.js、vm/jsdom/sdenv、WASM helper 和 browser-auto 兜底。
- `templates/scaffold/`：可复制到 target 的最小代码骨架，包括 `python-protocol`、`node-protocol`、`vm-sandbox`、`wasm-helper` 和 `browser-auto-fallback`。这些文件只提供通用入口、fixture 和目录约定，不写入真实目标材料。

### 浏览器工具层

浏览器工具用于侦察、hook、环境真值采集、差异比对和验收，不默认作为最终交付运行时。

- Camoufox MCP：默认首选浏览器工具层。用于 Firefox / Gecko 指纹基准、`compare_env`、分批 `evaluate_js`、pre-inject hook、Cookie 归因、服务端验收。强环境检测和沙箱补环境任务应优先采集 Camoufox 基准。
- CloakBrowser MCP：Chrome / Chromium 指纹基准与可选自动化工具层。公开可用路线包括 `cloakbrowser-mcp`，它把 Playwright MCP 工具面桥接到 CloakBrowser Chromium binary；使用前先跑 `cloakbrowser-mcp doctor --json` 或等价检查。
- DevTools / Playwright MCP / 普通浏览器：兜底工具层。可用于基础观察和临时脚本注入，但缺少反检测基准或 Cookie 归因能力时要在 `notes.md` 里记录。

Camoufox 与 CloakBrowser 的环境样本必须分开记录。Camoufox 代表 Firefox 家族事实，CloakBrowser 代表 Chrome/Chromium 家族事实，补环境时不要混用 `window.chrome`、`navigator.userAgentData`、Firefox native code 格式等家族特征。

## 当前默认启用

默认只启用通用核心 skill：

```text
web-protocol-recovery
find-crypto-entry
browser-hook-snippets
ast-deobfuscate
env-patch
```

WAF、验证码、iv8 站点案例类 skill 保留在 `skills-library/`，需要时再启用，避免触发边界互相干扰。

## 使用约定

1. 不要把目标站点动态材料写入 skill 目录。
2. 动态材料统一放入 `js_reverse_cache/` 或 `targets/<site>/`。
3. skill 目录只保存方法论、模板脚本、references 和 evals。
4. 案例类 skill 默认不常驻启用。
5. 修改 skill 后优先在本项目内验证，再决定是否同步到全局 skill 目录。

## Target 目录规范

后续每个需要逆向的源都放在 `targets/` 下，并且每个源单独一个目录。目录保持轻量，不做过深拆分：

```text
targets/<source-name>/
├── source/       原始 JS、HTML、WASM、字体、页面源码等待分析材料
├── scripts/      解混淆、补环境、协议验证、辅助分析脚本，可含 env/ 和 replay/
├── samples/      任务元信息、请求/响应样本、证据 JSONL、cookie/header 样本
├── output/       最终完成的可运行程序、交付脚本、稳定复现代码
└── notes.md      逆向分析说明，必须维护，优先中文可读描述
```

### Target Artifact 契约

每个 `targets/<source-name>/` 既是目标工作区，也是可续做的 task artifact。新增目标时建议至少维护以下文件：

- `samples/task.json`：当前任务元信息、目标请求、阶段、成功判定和摘要。允许覆盖更新。
- `samples/network.jsonl`：关键请求、响应、headers/body、状态码和响应特征。按证据追加。
- `samples/scripts.jsonl`：关键脚本、initiator、函数位置、候选入口、`source -> entry -> builder -> writer -> sink` 链路和桥接层线索。按证据追加。
- `samples/runtime-evidence.jsonl`：hook 命中、中间值、对象字段、cookie/storage、环境读取、first divergence 线索。按证据追加。
- `samples/timeline.jsonl`：每轮“做了什么 / 看到什么 / 下一步”的续做记录；阶段切换或子 skill 转交时写入交接卡。按阶段追加。
- `scripts/env/`：Node local rebuild 的入口、环境补丁、polyfill 和固定上下文，只在进入补环境阶段后维护。
- `scripts/replay/actions.json`：复杂页面触发动作记录，只在触发步骤容易遗忘时维护。
- `output/fixtures.json`、`output/pure-*.js`、`output/pure_*.py`：通过 local rebuild 后再沉淀的固定夹具和纯算法 / 外部宿主版本。

阶段最小落地要求：

- Observe：至少维护 `samples/task.json`、`samples/network.jsonl`、`samples/scripts.jsonl` 和 `notes.md`。
- Capture：新增或更新 `samples/runtime-evidence.jsonl`，必要时补 `scripts/replay/actions.json`。
- Rebuild / Patch：维护 `scripts/env/*`、`samples/timeline.jsonl` 和 `notes.md`，每轮记录 first divergence。
- Pure / Port：维护 `output/fixtures.json` 与可运行实现，并在 `notes.md` 写清验收结果。

请求链记录重点不是写长篇分析，而是证明字段链路：`source -> entry -> builder -> writer -> sink`。如果正常态和风控态分叉，必须在证据中拆开记录，不能合并成一个模糊结论。

`notes.md` 是每个源的核心沉淀，不应只堆代码。它需要清楚记录：

1. 目标源信息：站点、接口、厂家/防护类型、入口页面或 API。
2. 逆向方式：使用了入口定位、hook、AST 解混淆、补环境、iv8、纯 Python、协议恢复中的哪条路线。
3. 厂家和防护判断：例如瑞数、腾讯 WAF、极验、易盾、数美、站点自研签名等，以及判断依据。
4. 关键值：sign、token、cookie、header、nonce、timestamp、payload、轨迹、动态 seed 等。
5. 计算/分析过程：关键值从哪里来、如何定位、如何计算、如何验证。
6. 难点和风险：混淆、环境检测、会话绑定、时间戳、IP/账号绑定、验证码、响应解码等。
7. 验证结论：当前是否可复现、验证请求结果、剩余问题、下一步建议。

不要把大量源码直接粘进 `notes.md`。代码放 `scripts/` 或 `output/`，`notes.md` 只引用文件路径并解释其作用。

## 常用命令

列出库中 skill：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\list-skills.ps1
```

启用一个库中 skill 到 Agent、Codex 和 Claude Code 项目级目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\enable-skill.ps1 -Name jd-h5st-iv8
```

停用一个项目级 skill：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\disable-skill.ps1 -Name jd-h5st-iv8 -Targets codex,claude
```

审查 skill 目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\audit-skills.ps1
```

创建一个新的逆向源目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name xhs-homefeed
```

按复现形态初始化代码骨架：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-python -Runner python-protocol
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-node -Runner node-protocol
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-vm -Runner vm-sandbox
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-wasm -Runner wasm-helper
powershell -ExecutionPolicy Bypass -File .\tools\new-target.ps1 -Name demo-browser -Runner browser-auto-fallback
```
