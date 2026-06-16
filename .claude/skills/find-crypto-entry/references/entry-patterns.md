# 入口定位模式

本文件用于定位请求签名、token、cookie、安全 header、WebSocket 消息字段或响应解密入口。目标是交付可继续分析的入口证据，不在本 skill 内完成全部算法恢复。

## 核心模型

入口定位要围绕真实线路上的字段，按以下链路拆开：

```text
source -> entry -> builder -> writer -> sink
```

- `source`：真实输入来源，例如上游响应、cookie、storage、时间、随机数、环境指纹、WASM 内存、worker 消息、用户输入。
- `entry`：触发 builder 的入口，例如点击事件、生命周期回调、请求拦截器、bootstrap 回包、worker 回包。
- `builder`：组装、签名、加密、序列化或封包逻辑。
- `writer`：最终写入点，例如 header/body/query/cookie/WebSocket frame/storage/隐藏 DOM 字段。
- `sink`：真实发送到线路上的请求、消息或状态消费点。

定位完成不是“找到了一个疑似函数名”，而是至少证明 writer 或 builder 和真实 sink 有关系。

## 常见架构

### 业务代码直接赋值

典型形态：

```javascript
headers["x-sign"] = encrypt(payload)
config.params.sign = makeSign(config.params)
```

搜索顺序：

1. 参数名、header 名、cookie 名。
2. API path 片段。
3. 附近请求函数或提交函数。
4. 可见的加密、摘要、编码函数名。

交付重点：

- 请求函数。
- 赋值位置。
- 加密调用路径。
- 输入字段来源。

### 请求拦截器统一加签

常见于 axios、fetch wrapper、umi request、uni-app request、自研 SDK。

搜索顺序：

1. `interceptors.request.use`。
2. `setRequestHeader` / `headers` / `config.headers`。
3. API 白名单、path matcher、cache options。
4. 共享 request wrapper import。

不要停在拦截器注册处。要继续追到最终写入字段的 writer，以及 writer 调用的 builder。

### 外部安全 SDK

业务 bundle 可能只调用一个全局 SDK，真实算法在独立混淆脚本里。

搜索顺序：

1. 业务侧全局对象或 SDK 名称。
2. SDK init / register / config。
3. 注册路径、白名单、开关、缓存配置。
4. 返回或注入安全字段的方法。

如果 SDK 文件重混淆，入口定位到 SDK 方法即可交接给 `ast-deobfuscate` 或 `env-patch`，不要在本 skill 内强行还原完整算法。

### Challenge / 动态 Cookie

信号：

- 首屏或前置请求返回 `412`、`202`、`204`、跳转或 challenge HTML。
- 页面包含 `$_ts`、`r2mKa`、`cookie_s`、`cookie_t`、`meta[r='m']` 等线索。
- 目标字段以 `document.cookie`、Set-Cookie 或二跳请求消费形式出现。

这不是普通 sign 函数问题。应先证明 challenge 链路：

- 哪个响应播种状态。
- 哪个脚本或 runtime 写 cookie。
- 哪个后续请求消费 cookie。
- 正常态和风控态在哪里分叉。

若证据指向瑞数固定链路，按任务目标交给 `rs-reverse` 或对应 WAF skill。

### 环境读取型 JSVMP

信号：

- 没有清晰的 `sign()` 单点函数。
- 输出依赖解释器执行、副作用、对象属性读取或宿主 API。
- 请求前看不到显式赋值，但 cookie/header/storage 变化。

这类任务不要伪造一个单点函数结论。应交付：

- 调度入口。
- 关键环境读取点。
- 已确认的 writer 或最终 sink。
- 推荐后续进入 `env-patch`、`ast-deobfuscate` 或协议恢复主线。

## 动态验证

静态搜索不够时，优先按真实请求反推：

1. 对目标 API 设置 XHR/fetch 断点。
2. 看请求 wrapper 帧，不只看框架底层。
3. 沿调用栈找到 writer。
4. 在目标调用帧里求值当前 request config、headers、body、SDK 实例和候选返回值。
5. 记录脚本 URL、行列号、函数名、调用路径和样本编号。

避免反复 step into 框架、runtime 或 vendor 代码。通常检查当前帧和上层业务帧更快。

## 调试降噪

暂停点落入框架或 runtime 时：

- 黑盒 `jquery`、`react`、`vue`、`axios`、`lodash`、`node_modules`、`vendor`、webpack runtime。
- 用 URL 片段设置条件 XHR/fetch 断点，不要全局打断所有请求。
- Watch 只盯当前问题需要的值：最终 header、request config、SDK 实例、时间种子、cookie/storage key、候选函数输出。
- Watch 必须在目标调用帧求值，不能只在顶层页面上下文求值。
- 交互型签名可用 click / submit / timer / WebSocket 事件辅助定位。

这些是定位手段，不是最终交付物。

## 加密类型快速判断

入口已定位但算法类型不清时，用以下信号分类：

- `CryptoJS.AES/DES/TripleDES/RC4`：关注 mode、padding、iv、salt。
- `crypto.subtle.encrypt/sign/digest/importKey`：关注算法对象的 name、hash、iv、key usage。
- 256 项表、S-box、密集位运算、固定 block 循环：可能是对称加密或自定义 hash。
- `modPow`、`modInverse`、`gcd`、素数检查：可能是 RSA/ECC 类大数逻辑。
- MD5/SHA/AES 常量只能帮助分类，不能证明最终入口。

分类只用于选择下一步 skill，不要把本 skill 扩展成完整算法恢复。

## 完成模板

```text
入口位置：
- 参数 / 字段：
- sink：
- writer：
- builder：
- entry：
- source：
- 脚本：
- 位置：
- 函数：
- 调用路径：
- 加密类型：标准算法 / WebCrypto / 自定义算法 / 环境读取型 / 未知需解混淆
- 入口类别：业务直赋值 / 拦截器统一加签 / 外部 SDK / challenge 动态 cookie / 环境读取型 JSVMP
- 样本状态：正常态 / 风控态 / 未知态
- 请求契约：method + url pattern + 字段所在位置
- 运行种子：cookie/storage/header/时间/随机数的键名、格式或参与状态
- 证据落地：
  - 请求证据：targets/<source-name>/samples/network.jsonl
  - 脚本证据：targets/<source-name>/samples/scripts.jsonl
  - 运行时证据：targets/<source-name>/samples/runtime-evidence.jsonl（如已采样）
  - 续做记录：targets/<source-name>/samples/timeline.jsonl
- 下一步：ast-deobfuscate / env-patch / browser-hook-snippets / rs-reverse / web-protocol-recovery / 已完成
```

完成标准：后续 skill 不看聊天记录，也能从 target artifact 继续接手。
