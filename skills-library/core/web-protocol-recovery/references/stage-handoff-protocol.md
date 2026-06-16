# 阶段交接协议

本文件用于阶段切换时保留上下文，防止长任务中出现“前面证明过什么、还缺什么”丢失。

它不是一个独立阶段，而是在 `Observe -> Capture -> Rebuild -> Patch -> Pure -> Port` 或子问题 skill 交接时触发。

## 何时写交接

出现以下情况时必须写交接：

- 当前阶段发生变化。
- 证据推翻了之前的关键判断，需要回退阶段。
- 从 `web-protocol-recovery` 转给 `find-crypto-entry`、`ast-deobfuscate`、`env-patch`、`browser-hook-snippets`、`rs-reverse` 等子 skill。
- 从子 skill 回到协议恢复主线。
- 会话即将中断，后续需要续做。

## 交接卡格式

建议把交接卡写入 `samples/timeline.jsonl`，并在 `notes.md` 中保留中文摘要。

```json
{
  "stage": "handoff",
  "from": "Observe",
  "to": "Capture",
  "sampleId": "S-001",
  "provenFacts": {
    "targetRequest": "POST /api/example",
    "sink": "header x-sign",
    "writer": "main.js: setRequestHeader",
    "builder": "buildSign(payload)",
    "entry": "submit click",
    "source": ["timestamp", "nonce", "bootstrap seed"],
    "sampleState": "normal"
  },
  "openQuestions": [
    "buildSign 内部是否读取 cookie",
    "nonce 是否一次性"
  ],
  "invalidatedAssumptions": [],
  "nextAction": "对 buildSign 做最小 hook，记录输入输出"
}
```

如果任务很简单，也可以在 `notes.md` 中使用紧凑格式：

```markdown
阶段交接：Observe -> Capture
- 已证明：POST /api/example，x-sign 由 main.js 请求拦截器写入。
- 未闭环：builder 输入边界、cookie 是否参与。
- 下一步：hook builder 输入输出。
```

## 已证事实规则

交接中的 `provenFacts` 只能写有证据支撑的事实。每个事实应能回溯到：

- 抓包样本。
- request initiator。
- hook 输出。
- 断点现场。
- response body / Set-Cookie。
- 本地固定输入输出验证。

猜测只能写进 `openQuestions`，不能写进 `provenFacts`。

## 必填事实

从不同阶段出来时，至少携带：

| 来源阶段 | 必填事实 |
| --- | --- |
| Observe | 目标请求、触发动作、候选脚本、样本状态 |
| Capture | writer/builder/entry/source、运行时样本、字段对齐情况 |
| Rebuild | 本地入口、固定上下文、当前运行结果、first divergence |
| Patch | 修复项、分歧是否前移、浏览器真值对齐、验收状态 |
| Pure | fixture、输入边界、纯算输出、漂移边界 |
| Port | 外部宿主实现、跨语言对齐、服务端验收 |

## 被推翻假设

如果后续证据推翻了旧结论，必须写清：

- 哪个结论被推翻。
- 新证据是什么。
- 是否需要回退阶段。
- 哪些文件已更新。

示例：

```json
{
  "stage": "handoff",
  "from": "Patch",
  "to": "Observe",
  "invalidatedAssumptions": [
    "原先认为 x-token 由本地 builder 生成；新证据显示它来自上游 Set-Cookie"
  ],
  "nextAction": "回到请求链，补上 Set-Cookie 上游依赖"
}
```

## 子 skill 交接

转给子 skill 时，交接卡要写清“为什么转”：

- `find-crypto-entry`：还缺脚本 URL、函数、writer/builder 边界。
- `ast-deobfuscate`：边界已证明，但混淆阻挡读取或抽取。
- `env-patch`：入口已知，本地运行发生环境分歧。
- `browser-hook-snippets`：只缺最小采样脚本。
- `rs-reverse`：证据指向瑞数固定骨架、首跳/二跳 cookie 或 runtime 观察。

子 skill 完成后，必须把返回的入口、样本、分歧或结论写回 target artifact。

## 完成标准

一个交接合格的标准是：后续读者不看聊天记录，也能从 target 目录回答：

1. 已经证明了什么。
2. 哪些假设被推翻。
3. 当前缺口属于哪个阶段。
4. 下一步最小动作是什么。
