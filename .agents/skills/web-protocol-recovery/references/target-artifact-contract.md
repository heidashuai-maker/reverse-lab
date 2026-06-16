# Target Artifact Contract

本文件定义 `reverse-lab` 的目标证据契约。它吸收了 task artifact 的工程思想，但不引入新的顶层 `artifacts/tasks/` 目录；所有目标材料仍落在 `targets/<source-name>/`。

## 基本原则

1. 每个结论都要能在 target 目录中找到对应证据。
2. 证据文件优先追加，当前状态文件允许覆盖。
3. 浏览器观察、运行时采样、本地重建、补环境、纯算法提纯要分阶段沉淀。
4. `notes.md` 是中文可读报告，不替代结构化证据文件。
5. 敏感值、cookie、账号状态和真实业务样本共享前必须脱敏。

## 目录映射

```text
targets/<source-name>/
├── source/
├── samples/
│   ├── task.json
│   ├── network.jsonl
│   ├── scripts.jsonl
│   ├── runtime-evidence.jsonl
│   └── timeline.jsonl
├── scripts/
│   ├── env/
│   │   ├── entry.js
│   │   ├── env.js
│   │   ├── polyfills.js
│   │   └── capture.json
│   └── replay/
│       └── actions.json
├── output/
└── notes.md
```

`source/` 放原始输入材料，例如 JS、HTML、WASM、字体和页面源码。`samples/` 放请求、响应、cookie、headers、证据 JSONL 和固定样本。`scripts/` 放分析和本地重建脚本。`output/` 放最终可运行程序、稳定复现代码、固定夹具和纯算法结果。

## 文件职责

### `samples/task.json`

记录当前任务元信息：

- `taskId` / `slug`
- 目标页面、目标接口和触发动作
- 当前阶段：`Observe` / `Capture` / `Rebuild` / `Patch` / `Pure` / `Port`
- 成功判定：本地重建、服务端验收、浏览器真值对齐
- 1 到 3 句当前摘要

该文件保存“当前最新状态”，允许覆盖更新。

### `samples/network.jsonl`

每行记录一条关键网络证据，建议包含：

- 时间或轮次
- method、URL、请求位置
- 关键 query/body/header/cookie 字段摘要
- 响应状态、响应特征、是否疑似真实业务数据
- requestId、initiator 或触发动作线索

该文件只追加，不应频繁覆盖。

### `samples/scripts.jsonl`

每行记录一条脚本或入口证据，建议包含：

- 脚本 URL、本地文件名或 bundle/chunk 名
- 行列号、函数名、模块 ID、调用链
- 命中的关键词、参数名、API path 或 initiator 线索
- 当前判断：候选入口 / 已确认入口 / 误导线索
- 对动态字段建议补 `source -> entry -> builder -> writer -> sink` 中已证明的层级
- 对 WASM / Worker / Webpack runtime 建议补桥接层输入、输出、写回点和停止深度

该文件只追加。

### `samples/runtime-evidence.jsonl`

每行记录一次运行时采样，建议包含：

- hook / breakpoint / evaluate / proxy log 的来源
- 输入、输出、中间值的形态摘要
- 读取了哪些 cookie、storage、navigator、canvas、WebCrypto、WASM 或时间随机数
- 是否与网络最终值对齐

该文件只追加。不要把完整敏感 cookie、账号 token 或大体积响应直接写入；必要时写文件路径和脱敏摘要。

### `samples/timeline.jsonl`

每行记录一次阶段推进：

- 做了什么
- 看到什么
- 当前结论是否变化
- 下一步最小动作
- 阶段切换或子 skill 转交时，写入 `stage=handoff` 的交接卡
- 旧假设被推翻时，写入被推翻的结论和回退阶段

该文件用于跨轮续做，建议每个重要回合追加一条。

### `scripts/env/*`

用于 Node local rebuild：

- `entry.js`：本地运行入口，加载目标脚本和固定上下文。
- `env.js`：最小宿主对象、环境补丁和代理诊断。
- `polyfills.js`：窄 polyfill、`safeFunction`、watch、日志等辅助能力。
- `capture.json`：固定输入、seed、cookie/storage 摘要、浏览器真值样本。

这些文件表示“当前可运行状态”，允许覆盖，但每次覆盖后应在 `timeline.jsonl` 或 `notes.md` 写清原因。

### `scripts/replay/actions.json`

记录复杂页面触发动作，例如导航、点击、输入、滚动、等待请求或 WebSocket 建连。只有触发步骤有复现价值时才维护。

### `output/*`

只放已经稳定的交付或提纯结果：

- `fixtures.json`：固定输入、runtimeContext、期望输出。
- `pure-*.js`：Node 可读纯算法实现。
- `pure_*.py`：Python 或其他宿主实现。
- 最终采集器、解码器、签名 helper、样例输出。

## 阶段最低产物

### Observe

目标是确认真实请求、候选脚本和触发动作。最低产物：

- `samples/task.json`
- `samples/network.jsonl`
- `samples/scripts.jsonl`
- `notes.md`

没有这些文件，不应宣称 Observe 完成。

Observe 完成时还应能说清：

- 目标字段的 `source -> entry -> builder -> writer -> sink` 已闭环到哪一层。
- 当前样本是正常态、风控态还是未知态。
- 上游依赖已展开，还是仍有未闭环项。

### Capture

目标是用最小 hook 或调试拿到运行时样本。最低新增：

- `samples/runtime-evidence.jsonl`
- 必要时更新 `samples/network.jsonl` 和 `samples/scripts.jsonl`
- 复杂触发时补 `scripts/replay/actions.json`

运行时证据不能只留在聊天记录里。

### Rebuild

目标是形成本地可运行入口。最低产物：

- `scripts/env/entry.js`
- `scripts/env/env.js`
- `scripts/env/polyfills.js`
- `scripts/env/capture.json`
- `samples/timeline.jsonl`
- `notes.md`

如果没有稳定入口文件，不应把任务状态写成 Rebuild 已完成。

### Patch

目标是按 first divergence 逐项补环境。每轮必须记录：

- 本轮 first divergence
- 修复的最小因果单元
- 修复后本地输出是否前移
- 是否与浏览器真值对齐
- 是否服务端验收通过
- 当前分歧属于缺对象、缺状态、反调试、不稳定源还是风控分支

记录位置：

- `samples/timeline.jsonl`
- `samples/runtime-evidence.jsonl`
- `notes.md`
- 必要时更新 `scripts/env/*`

### Pure / Port

进入条件是 local rebuild 已经通过并有稳定样本。最低产物：

- `output/fixtures.json`
- `output/pure-*.js`
- 可选 `output/pure_*.py`
- `notes.md` 中的输入边界、漂移边界和验收记录

如果没有固定夹具，不应宣称完成纯算法提纯或跨语言移植。

## 追加与覆盖规则

适合追加：

- `samples/network.jsonl`
- `samples/scripts.jsonl`
- `samples/runtime-evidence.jsonl`
- `samples/timeline.jsonl`

适合覆盖：

- `samples/task.json`
- `scripts/env/entry.js`
- `scripts/env/env.js`
- `scripts/env/polyfills.js`
- `scripts/env/capture.json`
- `scripts/replay/actions.json`

适合持续修订：

- `notes.md`

## 交付门禁

最终交付前至少回答：

1. 真实请求是什么，证据在哪一行或哪个文件。
2. 哪些字段是动态状态，来源是什么。
3. local rebuild 是否跑通，first divergence 是否记录。
4. 浏览器真值是否与本地输出对齐。
5. 服务端验收是否通过，是否可重复。
6. 最终产物保存在 `output/` 的哪个文件。
