# 协议恢复流程总览

本文是最短端到端执行地图。目标是把 Web/JS 逆向任务收束成可续做、可验证、可交付的工程流程。

## 核心原则

- 先观察，再采样。
- 优先最小 hook，断点作为后手。
- 先确认浏览器真值，再做本地重建。
- 每个结论都写入 target artifact，不只留在对话里。
- local rebuild 通过后，再做纯算法提纯或 Python 移植。

## Startup Gate

正式分析前先完成：

1. 确认目标目录：`targets/<source-name>/`。
2. 确认缓存目录：临时素材进入 `js_reverse_cache/`，长期证据进入 target。
3. 阅读 `references/target-artifact-contract.md`，明确本轮证据写入位置。
4. 阅读 `references/request-chain-evidence.md`，确认目标请求、字段来源和样本状态是否已经闭环。
5. 分类目标：`signer-gated` / `verifier-gated` / `decode-gated` / `session-gated`。
6. 明确最终交付形态：纯 Python、Python + 极小 JS helper、Python + 极小 WASM helper，或本地 bootstrap executor。

## Phase 1: Observe

目标：确认真实请求、关键脚本和触发动作。

必须回答：

- 真实请求 URL、method、参数位置是什么。
- 请求由哪个页面动作或生命周期触发。
- initiator、候选脚本、候选函数在哪里。
- 响应是否是真实业务数据，还是 challenge / wrapper / decode 前数据。
- 目标字段的 `source -> entry -> builder -> writer -> sink` 当前闭环到哪一层。
- 当前样本是正常态、风控态还是未知态。

最低落地：

- `samples/task.json`
- `samples/network.jsonl`
- `samples/scripts.jsonl`
- `notes.md`

## Phase 2: Capture

目标：用最小侵入方式拿到运行时证据。

优先采样：

- fetch / XHR 最终入参。
- 请求拦截器或 SDK 写入点。
- sign/token/cookie/header 的输入输出。
- 时间、随机数、cookie/storage、UA、WebCrypto、WASM、canvas 等环境依赖。

最低落地：

- `samples/runtime-evidence.jsonl`
- 必要时更新 `samples/network.jsonl`、`samples/scripts.jsonl`
- 复杂页面动作写入 `scripts/replay/actions.json`

## Phase 3: Rebuild

目标：把浏览器证据转成本地 Node 可运行入口。

必须固定：

- 目标脚本加载顺序。
- 入口函数或触发点。
- 固定上下文、seed、cookie/storage 摘要、浏览器真值样本。
- 当前失败点或第一处不一致。

最低落地：

- `scripts/env/entry.js`
- `scripts/env/env.js`
- `scripts/env/polyfills.js`
- `scripts/env/capture.json`
- `samples/timeline.jsonl`
- `notes.md`

## Phase 4: Patch

目标：按 first divergence 最小补环境，直到本地输出与浏览器真值对齐。

进入前先读 `references/runtime-divergence-diagnosis.md`，不要把缺对象、缺状态、反调试、不稳定源和风控分支混成一个“补环境”问题。

每轮只修一个最小因果单元：

- 缺失对象或属性。
- 行为不一致的 API。
- 编码、时间、随机数、cookie/storage 或 WebCrypto 差异。
- WASM / worker / bootstrap 加载顺序差异。

每轮记录：

- first divergence 是什么。
- 修复了什么。
- 输出是否前移。
- 浏览器真值是否对齐。
- 服务端是否验收。

最低落地：

- `samples/timeline.jsonl`
- `samples/runtime-evidence.jsonl`
- `notes.md`
- 必要时更新 `scripts/env/*`

## Phase 5: Pure / Port

目标：把已跑通的本地链路提纯成稳定交付。

进入条件：

- local rebuild 已通过。
- 至少有一组稳定 fixture。
- 已记录浏览器真值或服务端验收结果。

最低落地：

- `output/fixtures.json`
- `output/pure-*.js`
- 可选 `output/pure_*.py`
- 最终采集器或 helper
- `notes.md` 中写清输入边界、漂移边界和验收结论

## 阶段切换规则

- 未确认真实请求，不进入补环境。
- 没有运行时证据，不写大面积浏览器 shim。
- local rebuild 未通过，不进入 pure extraction。
- 没有固定 fixture，不做跨语言移植。
- 任一阶段出现不一致，回退到最早出现分叉的阶段。
- 每次阶段切换或转交子 skill，按 `references/stage-handoff-protocol.md` 写交接卡。

## 交付检查

交付前确认：

1. 真实请求和动态字段有证据文件支撑。
2. 本地 helper 或采集器不依赖浏览器 profile。
3. 固定输入输出自检可重复。
4. 服务端验收至少通过一次，最好重复 2 到 3 次。
5. 代码放 `scripts/` 或 `output/`，说明写在 `notes.md`。
