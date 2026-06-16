# 桥接层契约：WASM / Worker / Webpack

WASM、Worker 和 Webpack runtime 的共同点是：真实逻辑可能不在主线程直观代码里，但输入、输出和写回边界一定存在。逆向时优先证明桥接契约，而不是一开始就全量反编译。

## 通用判断

先回答四个问题：

1. 输入从哪里进入桥接层。
2. 桥接层如何调用内部逻辑。
3. 输出在哪里返回。
4. 输出如何写回请求、cookie、storage、消息或内存。

如果这四个问题已经足够支持重放或验证，不必继续下钻内部实现。

## Worker 桥接

优先确认：

- worker 来源：独立文件、Blob URL、字符串拼接、动态 import。
- 主线程发给 worker 的消息结构。
- worker 返回的消息结构。
- 是否携带一次性 challenge、设备种子、会话状态或二跳 cookie。
- 返回值在哪里被消费：请求字段、header、cookie、WebSocket frame、storage。

建议记录到 `samples/scripts.jsonl`：

```json
{
  "role": "worker-bridge",
  "workerSource": "worker.js / blob / string-assembled",
  "mainToWorker": "message shape",
  "workerToMain": "message shape",
  "stateCarriers": ["cookie", "storage", "device seed"],
  "writeBack": "headers['x-sign'] / body.sign / postMessage callback",
  "stopDepth": "bridge contract enough | need deeper recovery",
  "notes": "为什么停在桥接层或为什么继续下钻"
}
```

## WASM 桥接

优先确认：

- `instantiate` / `instantiateStreaming` 调用位置。
- imports 需要哪些宿主函数、内存、table 或环境状态。
- exports 暴露哪些函数。
- JS wrapper 如何打包参数、写入内存、读取返回值。
- 返回值是最终结果，还是又被 JS wrapper 包装。

建议记录到 `samples/scripts.jsonl`：

```json
{
  "role": "wasm-bridge",
  "instantiate": "script and location",
  "imports": ["env.xxx", "memory", "table"],
  "exports": ["sign", "encode"],
  "paramPacking": "string -> utf8 memory -> pointer/length",
  "resultUnpacking": "pointer/length -> string",
  "writeBack": "query.sign",
  "stopDepth": "wrapper reuse | export contract | need wasm analysis",
  "notes": "是否需要反编译 wasm"
}
```

判断原则：

- 如果 wrapper 输入输出清楚，优先复用 wrapper 或导出函数。
- 如果结果依赖 WASM 内部状态、内存变更或隐藏序号，再进入更深层恢复。
- 不要因为出现 `.wasm` 就默认要反编译整个模块。

## Webpack / Runtime 桥接

优先确认：

- runtime 启动入口。
- chunk / lazy loading 触发点。
- 目标业务 module。
- runtime shell 与业务 module 的边界。
- module 导出对象、闭包状态和调用方。

常见误区：

- 长时间停在 webpack runtime helper，不进入业务 module。
- 只搜索明文参数名，忽略模块 ID、chunk 名、import/require 边界。
- 把 runtime 装载问题误判为算法问题。

建议记录：

```json
{
  "role": "webpack-module-boundary",
  "runtimeEntry": "webpack bootstrap or chunk loader",
  "chunk": "chunk name/hash",
  "moduleId": "module id or path hint",
  "businessExport": "exported function/object",
  "caller": "request wrapper / SDK / event handler",
  "sharedState": ["closure state", "module cache", "runtime config"],
  "stopDepth": "module boundary enough | need module recovery",
  "notes": "runtime 层与业务层如何分开"
}
```

## 是否继续下钻

可以停在桥接层的信号：

- 输入、输出、写回点已清楚。
- 能用固定样本验证桥接层输出。
- 下游只需要调用或复用该桥接层。
- 深挖内部不会改善协议恢复结论。

需要继续恢复的信号：

- 输出依赖隐藏状态，无法稳定复现。
- 只有桥接外壳，内部关键输入仍未知。
- 桥接层里还有 JSVMP、动态代码、反调试或风控分支。
- 需要纯算法移植，不能保留黑盒 helper。

## 交付要求

桥接层分析完成时，应在 target artifact 中能看到：

- 桥接类型：Worker / WASM / Webpack runtime / mixed。
- 输入、输出、写回点。
- 状态载体：cookie、storage、内存、seed、session、challenge。
- 停止深度：复用桥接层、恢复导出契约、提取关键算子、还是继续深挖。
- 固定样本验证结果。

这些内容建议写入：

- `samples/scripts.jsonl`
- `samples/runtime-evidence.jsonl`
- `notes.md`
