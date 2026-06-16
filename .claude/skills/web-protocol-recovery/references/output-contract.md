# 输出契约

协议恢复任务的输出必须能让人或后续 Agent 直接续做。不要只给模糊结论；每个关键判断都要指向 `targets/<source-name>/` 下的证据文件。

## 阶段报告

每次完成一个有意义阶段后，按以下结构汇报：

```markdown
阶段：
- 当前阶段：Observe / Capture / Rebuild / Patch / Pure / Port
- 状态：active / partial / pass / blocked
- 目标目录：targets/<source-name>/

已确认：
- 真实请求：
- 关键脚本：
- 触发动作：
- 动态字段：

未确认：
- 入口缺口：
- 环境缺口：
- 验收缺口：

证据位置：
- network: samples/network.jsonl
- scripts: samples/scripts.jsonl
- runtime: samples/runtime-evidence.jsonl
- timeline: samples/timeline.jsonl
- notes: notes.md

下一步：
- 只写一个最小动作
```

## Observe 输出要求

必须说明：

- 真实请求候选和最终判断。
- 请求 method、URL、参数位置、响应特征。
- initiator、候选脚本、候选函数或搜索线索。
- 页面触发动作。
- 哪些线索可能是误导。

必须落地：

- `samples/task.json`
- `samples/network.jsonl`
- `samples/scripts.jsonl`
- `notes.md`

## Capture 输出要求

必须说明：

- 使用了哪种采样方式：hook、preload hook、XHR/fetch 断点、evaluate、proxy log。
- 采样点输入、输出和中间值的形态。
- 采样结果是否能解释最终请求字段。
- 是否出现观察者效应。

必须落地：

- `samples/runtime-evidence.jsonl`
- 必要时更新 `samples/network.jsonl` 和 `samples/scripts.jsonl`
- 复杂触发动作写入 `scripts/replay/actions.json`

## Rebuild / Patch 输出要求

必须说明：

- local rebuild 入口在哪里。
- 固定上下文和浏览器真值来自哪里。
- 当前 first divergence 是什么。
- 本轮补了哪个最小因果单元。
- 修复后本地输出是否前移。
- 是否与浏览器真值对齐。

必须落地：

- `scripts/env/entry.js`
- `scripts/env/env.js`
- `scripts/env/polyfills.js`
- `scripts/env/capture.json`
- `samples/timeline.jsonl`
- `notes.md`

## Pure / Port 输出要求

必须说明：

- 输入边界：哪些值来自算法输入，哪些值来自环境状态。
- 固定夹具：输入、runtimeContext、期望输出。
- Node pure 与 local rebuild 是否对齐。
- Python 或其他宿主版本是否对齐。
- 服务端验收是否通过。
- 漂移边界：哪些字段会随时间、会话、IP、账号或版本变化。

必须落地：

- `output/fixtures.json`
- `output/pure-*.js`
- 可选 `output/pure_*.py`
- 最终采集器或 helper
- `notes.md`

## 最终交付报告

最终报告必须包含：

- 目标家族和防护判断。
- 真实接口路径和动态状态分类。
- 浏览器证据、运行时证据、本地重建证据位置。
- Python 采集器与 JS/WASM helper 的职责拆分。
- 固定输入输出自检结果。
- 服务端验收结果和重复性。
- 最终产物路径。
- 剩余不稳定因素。

如果最终方案仍依赖浏览器、人工点击、浏览器 profile 或页面驱动回放，不能标记为协议恢复完成。
