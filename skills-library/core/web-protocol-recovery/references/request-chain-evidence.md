# 请求链证据方法

本文件用于把目标请求、字段来源、上游状态和下游消费记录成可验证证据。它不新增 `reverse-records/` 目录，而是落到当前 target 的 `samples/*.jsonl` 与 `notes.md`。

## 适用场景

出现以下情况时，先补请求链证据，再进入解混淆、补环境或协议重放：

- 目标请求还只是猜测，没有真实样本。
- 目标字段已出现，但不知道是谁写入。
- cookie、header、token、body 字段来自上游响应或挑战步骤。
- 正常请求和风控请求混在一起，分叉点不清楚。
- WebSocket、protobuf、GraphQL 或传输 wrapper 让真实业务字段被包裹。

## 核心模型

定位动态字段时按这条链路记录：

```text
source -> entry -> builder -> writer -> sink
```

- `source`：真实输入来源，例如上游响应、Set-Cookie、storage、时间、随机数、环境指纹、用户输入、WASM 内存、worker 消息。
- `entry`：触发 builder 的入口，例如点击、生命周期回调、请求拦截器、worker 回包、bootstrap 响应。
- `builder`：组装、签名、加密、序列化或封包逻辑。
- `writer`：最终写入点，例如 header/body/query/cookie/WebSocket frame/storage/隐藏 DOM 字段。
- `sink`：真实发到线路上的请求、消息或状态消费点。

不要只记录函数名。函数名只有在能证明它参与 `writer` 或 `builder` 时才有价值。

## 字段状态词

字段状态建议使用数组式标签，便于快速判断：

- `未知`
- `已知`
- `固定`
- `动态`
- `明文`
- `加密`
- `本地计算`
- `响应获取`
- `环境产生`
- `会话相关`
- `风控相关`
- `时序相关`
- `一次性`
- `可复用`
- `HttpOnly`

示例：

```json
["动态", "响应获取", "HttpOnly", "会话相关"]
```

## JSONL 落地建议

### `samples/network.jsonl`

记录请求链时，每条关键请求建议包含：

```json
{
  "stage": "Observe",
  "sampleId": "S-001",
  "evidenceId": "E-001",
  "role": "target-request",
  "method": "POST",
  "url": "https://example.com/api",
  "trigger": "点击提交按钮",
  "upstream": ["GET /bootstrap"],
  "responseShape": "200 JSON / risk HTML / encrypted text",
  "sampleState": "normal | risk | unknown",
  "notes": "为什么认为这是目标请求"
}
```

### `samples/scripts.jsonl`

记录写入边界、候选入口和调用链：

```json
{
  "stage": "Observe",
  "sampleId": "S-001",
  "evidenceId": "E-002",
  "role": "writer-boundary",
  "script": "main.xxx.js",
  "location": "line:column or function hint",
  "callPath": "request -> interceptor -> signBuilder -> setHeader",
  "writer": "headers['x-sign'] = value",
  "builder": "signBuilder(payload)",
  "entry": "submit action",
  "source": ["timestamp", "nonce", "GET /bootstrap.response.seed"],
  "confidence": "confirmed | candidate | rejected",
  "notes": "证据来自 initiator / 断点 / hook / 源码阅读"
}
```

### `samples/runtime-evidence.jsonl`

记录运行时采样、字段对齐或分叉点：

```json
{
  "stage": "Capture",
  "sampleId": "S-001",
  "evidenceId": "E-003",
  "role": "runtime-sample",
  "probe": "hook fetch / hook function / breakpoint",
  "inputShape": "payload keys and lengths",
  "outputShape": "sign length / charset / segments",
  "consumedState": ["cookie: sid", "localStorage: seed", "Date.now"],
  "alignedToWire": "yes | no | partial",
  "notes": "与最终请求哪个字段对齐"
}
```

## 请求链最小闭环

一个请求链至少要能回答：

1. 目标请求是什么，样本在哪里。
2. 目标字段最后写入哪个 sink。
3. writer、builder、entry、source 分别是什么。
4. 哪些上游请求或状态参与了字段生成。
5. 当前样本是正常态、风控态还是未知态。
6. 哪些字段仍未闭环。

如果以上问题没回答完，不应直接进入大规模 AST 解混淆或 Node 补环境。

## 正常态与风控态分离

同一页面动作可能产生两条链：

- 正常态：返回业务数据或有效 token。
- 风控态：返回 challenge、空数据、412/403、跳转页、风险 cookie 或验证码分支。

记录时不要把两条链合并。至少在 `network.jsonl` 标记：

- `sampleState`
- 分叉前最后一个共同证据
- 分叉后第一个不同请求、响应或状态

## `notes.md` 摘要要求

`notes.md` 不需要堆 JSONL 内容，但应写清：

- 目标请求与关键字段。
- 已确认链路。
- 未闭环字段。
- 正常态 / 风控态判断。
- 下一步只写一个最小动作。

## 进入下一阶段的条件

可以进入入口定位 / recover / runtime 的条件：

- 目标请求来自真实样本。
- 关键字段至少有一个 writer 或候选 writer。
- 上游依赖已展开，或明确证明无上游依赖。
- 风控态和正常态没有混写成一个结论。

如果后续证据推翻前面结论，必须回到最早受影响的阶段，并在 `timeline.jsonl` 记录被推翻的假设。
