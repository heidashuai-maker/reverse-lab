# 逆向分析记录：<source-name>

## 1. 目标源信息

- 源名称：
- 目标站点 / 页面：
- 目标接口：
- 业务目标：
- 样本来源：
- 当前阶段：Observe / Capture / Rebuild / Patch / Pure / Port
- 当前状态：未开始 / 分析中 / 可复现 / 部分可复现 / 阻塞
- 本轮成功判定：

## 2. 厂家与防护判断

- 判断结论：
- 可能厂家 / 防护类型：
- 判断依据：
- 相关脚本 / 接口 / 字段：

## 3. 逆向方式

- 使用路线：入口定位 / 浏览器 hook / AST 解混淆 / Node 补环境 / iv8 / 纯 Python / 完整协议恢复
- 使用的 skill：
- 使用的浏览器工具层：Camoufox MCP / CloakBrowser MCP / DevTools / Playwright MCP / 其它
- 浏览器基准家族：Firefox / Chrome / unknown
- 为什么选择这条路线：
- 未采用路线及原因：

## 4. 目标请求与上下文

- 目标请求 method：
- 目标请求 URL：
- 参数位置：query / body / header / cookie / WebSocket frame / other
- 请求触发动作：
- initiator / 调用入口线索：
- 候选脚本：
- 响应特征：

## 5. 请求链证据

- 当前样本状态：正常态 / 风控态 / 未知态
- sink（最终消费点）：
- writer（最终写入点）：
- builder（组装 / 签名 / 加密 / 封包）：
- entry（触发入口）：
- source（真实输入来源）：
- 上游依赖：
- 未闭环字段：

## 6. 关键值与来源

| 名称 | 类型 | 来源 | 作用 | 是否动态 | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| sign/token/cookie/header |  |  |  |  |  |

## 7. 证据文件索引

- `samples/task.json`：任务元信息、当前阶段、目标请求、成功判定。
- `samples/network.jsonl`：关键请求和响应证据。
- `samples/scripts.jsonl`：关键脚本、initiator、函数位置和候选入口。
- `samples/runtime-evidence.jsonl`：hook、中间值、对象字段、环境读取证据。
- `samples/browser-env-camoufox.json`：Camoufox / Firefox 浏览器环境基准，可选。
- `samples/browser-env-cloakbrowser.json`：CloakBrowser / Chrome 浏览器环境基准，可选。
- `samples/local-env-baseline.json`：本地 vm/jsdom/sdenv 环境探针结果，可选。
- `samples/env-diff.json`：浏览器基准与本地环境差异，可选。
- `samples/timeline.jsonl`：阶段推进记录。
- `scripts/env/`：Node local rebuild 入口和环境补丁。
- `scripts/replay/actions.json`：页面触发动作序列。
- `output/`：最终可运行程序、固定夹具、纯算法或外部宿主实现。

## 8. 计算与分析过程

说明关键值是如何定位、如何计算、如何验证的。这里写清楚分析路径和证据，不要粘贴大段代码。

建议覆盖：

1. 真实请求如何确认。
2. 关键脚本或函数如何定位。
3. 动态输入有哪些，例如时间戳、nonce、cookie、localStorage、UA、referer、payload。
4. 计算过程的核心步骤。
5. 固定输入 / 输出验证结果。

## 9. 运行时证据与本地重建

- Runtime evidence 摘要：
- Local rebuild 入口：
- 当前运行结果：未开始 / 报错 / 可运行 / 已通过一次
- First divergence：
- 分歧类型：缺对象 / 缺状态 / 反调试 / 不稳定源 / 风控分支
- 浏览器基准文件：
- 本地基准文件：
- env diff 文件：
- 致命差异：
- 高危差异：
- 中危差异：
- UA 自洽判断：Firefox / Chrome / mixed / unknown
- 已修复环境缺口：
- 未修复环境缺口：
- 浏览器真值对齐：unknown / partial / pass

## 10. 桥接层与封装层

- Worker：无 / 有，输入输出与写回点：
- WASM：无 / 有，imports / exports / wrapper / 固定样本验证：
- Webpack runtime：无 / 有，chunk / module / business export：
- 传输 wrapper：无 / 有，改写字段：
- 是否继续下钻：复用桥接层 / 提取关键算子 / 继续恢复

## 10.1 复现路径选择

- 当前选择：纯 Python / 纯 Node.js / Node vm-jsdom-sdenv / WASM helper / TLS 指纹模拟 / browser-auto
- 选择依据：
- 已排除路径：
- 若为 browser-auto：
  - 为什么无法纯协议或本地 helper 复现：
  - headless 结果：
  - headed 结果：
  - 自动化运行成本与风险：
  - 后续继续逆向的最小方向：

## 11. 阶段交接记录

- 上一阶段：
- 当前阶段：
- 已证明事实：
- 未闭环问题：
- 被推翻假设：
- 下一步最小动作：

## 12. 样本与文件说明

- `source/`：
- `samples/`：
- `scripts/`：
- `output/`：

## 13. 难点与风险

- 混淆 / JSVMP：
- 环境检测：
- 会话绑定：
- IP / 账号 / Cookie 绑定：
- 验证码 / WAF：
- 响应解码：
- 其它风险：

## 14. 验证结果

- 验证时间：
- 验证请求：
- 返回状态：
- 返回特征：
- 是否可重复：
- 本地重建：unknown / partial / pass
- 服务端验收：unknown / partial / pass
- 浏览器样本对齐：unknown / partial / pass
- 失败样本：

## 15. 结论

- 当前结论：
- 可交付内容：
- 剩余问题：
- 下一步建议：只写一个最小动作
