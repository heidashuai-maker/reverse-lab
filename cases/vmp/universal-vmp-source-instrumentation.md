# 案例：通用 VMP 源码级插桩

> 难度：★★★★☆
> 反爬类型：签名型 / 行为型 / 混合型
> 首选路线：`find-crypto-entry` 定位 VMP 与入口，必要时转 `env-patch` 或 `web-protocol-recovery`
> 复现形态：源码级插桩学习入口与环境读取，后续选择纯算法、沙箱执行或协议恢复

## 适用范围

适用于算法被封装在 JavaScript 虚拟机 dispatch 循环中的目标，例如大体积混淆 JS、while-switch 分发、字节码数组、自定义解释器、签名函数无清晰源码的场景。

不适用于普通字符串数组混淆、入口已经明确且能直接跑通的轻量脚本。

## 技术指纹

- 单个 JS 文件通常 100KB+，含大字节码数组或长十六进制/字符串字节码。
- 出现 `while(true){switch(...)}`、`while(!![]){switch(...)}` 或类似 dispatch loop。
- 参数可能是固定长度 sign/token/header/cookie，常见 Base64 变体、hex、自定义字符表。
- 运行时可能读取 navigator、screen、cookie、storage、canvas、WebGL、时间和随机数。

## 参数特征（快速路由）

| 参数 / 字段 | 位置 | 长度 / 字符集 | 生成时机 | 判定价值 |
| --- | --- | --- | --- | --- |
| `sign` / `_signature` / `signature` | URL query / body / header | 32 hex、64 hex、128/192/256 字符等 | 请求发送前生成 | 中 |
| `token` / `x-token` / `x-sign` | header / URL query | Base64、hex、自定义字符表 | 预热后或请求前生成 | 中 |
| 动态 Cookie | Cookie | 长 token 或加密包 | challenge 后或 SDK 初始化后写入 | 中 |
| 固定长度长签名 | URL query / header | 128/192/256 字符，Base64 变体常见 | VMP 执行后输出 | 高 |
| 环境指纹字段 | query / body / storage | fp/device/browser id | SDK 初始化阶段生成 | 中 |

高置信度组合：固定长度动态字段 + 大体积 VMP 脚本 + dispatch loop。只有常见 `sign` 参数名不足以命中，需要同时确认 VMP 脚本或字节码解释器存在。

## 指纹检测规则

```text
快速检测：
1. 找最大 JS 文件，检查是否有 while-switch / dispatch loop。
2. 搜索 sign/token/header/cookie 写入点，确认是否只看到 VM wrapper。
3. 对业务请求打点，记录动态字段生成前后的调用栈。

高置信度：
- dispatch loop 明确存在；
- 关键动态字段由 VMP 执行后写入；
- 直接静态搜索无法看到算法主体。
```

## 已验证定位路径

```text
步骤 1：抓网络，锁定关键 JS 与目标请求。
步骤 2：搜索动态字段名和请求写入点，建立 source -> sink。
步骤 3：定位 dispatch loop 和 VM 入口函数。
步骤 4：做源码级插桩，记录 property read、method call、关键函数调用频次。
步骤 5：从 hot keys / hot methods 中判断是标准 crypto、环境指纹还是自定义算法。
步骤 6：按结果选择纯算法移植、Node/vm/jsdom 执行、或协议层重建。
```

## Phase 处理流程

### Phase 1：锁定 VMP 脚本

```text
1. 抓取首屏和业务请求网络日志。
2. 按 size、URL、加载顺序筛出最大/最可疑 JS。
3. 搜索 while-switch、dispatch、字节码数组、长 hex/base64 字符串。
4. 记录到 targets/<site>/samples/scripts.jsonl。
```

### Phase 2：建立动态字段链路

```text
source: URL/query/body/cookie/storage/server config/time/random/env
entry: VM wrapper / exported sign function / SDK init callback
builder: dispatch loop handlers / crypto helper / env collector
writer: URL param / request header / request body / cookie
sink: fetch / XHR / form submit / location replace
```

### Phase 3：源码级插桩

优先插桩源码中的对象读取、函数调用和写入点，而不是一上来反编译整个 VM。

```javascript
function installTap(root, name, log) {
  const value = root[name];
  Object.defineProperty(root, name, {
    configurable: true,
    get() {
      log({ type: "get", name, stack: new Error().stack });
      return value;
    },
  });
}

function wrapMethod(obj, name, log) {
  const raw = obj && obj[name];
  if (typeof raw !== "function") return;
  obj[name] = function wrappedMethod(...args) {
    log({ type: "call", name, args: args.map(String).slice(0, 5) });
    return raw.apply(this, args);
  };
}
```

### Phase 4：读取 hot path

```text
1. 高频 get: 判断是否读环境指纹。
2. 高频 call: 判断是否走标准 crypto / encoding。
3. 参数突变点: 找第一次从明文变成摘要、密文或编码串的位置。
4. 输出写入点: 确认 writer 是否稳定。
```

### Phase 5：选择还原路线

```text
标准 crypto 明显 -> 纯算法还原
入口参数少且不读环境 -> Node vm 最小执行
大量环境读取 -> env-patch browser-vs-local
请求链路复杂 -> web-protocol-recovery 端到端还原
```

## 链路图

```text
source: URL / query / body / cookie / storage / server config / time / random / env
entry: VMP wrapper / exported sign function / SDK init callback
builder: dispatch loop handlers / crypto helper / env collector / encoder
writer: URL param / request header / request body / cookie
sink: fetch / XHR / form submit / location replace
verification: fixed input diff + browser-vs-local + protocol replay
```

## 加密 / 编码 / 签名方案

- 算法：未知时不要硬猜；优先通过 hot methods 判断是否命中 WebCrypto、CryptoJS、MD5/SHA/HMAC/AES、CRC32、自定义表。
- 密钥来源：可能来自硬编码字节码、预热响应、cookie/storage、环境指纹或时间随机数。
- 输入字段：以插桩捕获的 first mutation 为准，记录 URL、body、timestamp、nonce、UA、cookie 是否参与。
- 输出字段：URL 参数、header、body 或 cookie，记录长度、字符集、稳定性和变化维度。
- 还原策略：能纯算法就纯算法；不能纯算法时保留最小 VM 或转 env-patch / web-protocol-recovery。

## 核心代码模板

### 标准 HMAC / hash 分支

```javascript
const crypto = require("crypto");

function genSign({ url, body = "", ts, nonce, secret }) {
  const payload = [url, body, ts, nonce].join("|");
  return crypto
    .createHmac("sha256", secret)
    .update(payload)
    .digest("base64url");
}
```

### Node VM 最小执行分支

```javascript
const fs = require("fs");
const vm = require("vm");

function createSandbox(envFacts) {
  return {
    console,
    navigator: envFacts.navigator,
    location: envFacts.location,
    document: envFacts.document,
    Date,
    Math,
  };
}

function loadSign(scriptPath, envFacts) {
  const code = fs.readFileSync(scriptPath, "utf8");
  const sandbox = createSandbox(envFacts);
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { timeout: 5000 });
  return sandbox.__export_sign;
}
```

## 还原分支

| 观察结果 | 推荐路线 |
| --- | --- |
| hot methods 命中 WebCrypto / CryptoJS / 标准 hash | 尝试纯算法还原 |
| hot keys 很少，入口参数明确 | 提取最小 JS 到 Node vm |
| hot keys 很多，签名长度正确但服务端拒绝 | 进入 `env-patch` 做浏览器环境对齐 |
| 请求链路还有预热、cookie、TLS 绑定 | 进入 `web-protocol-recovery` 端到端恢复 |

## 验证方法

- 固定输入验证：同一 URL、body、时间、nonce 下，浏览器输出和本地输出一致。
- 变化维度验证：分别修改 URL、body、timestamp、cookie，确认输出变化方向与浏览器一致。
- first mutation 验证：定位明文第一次变成 hash、密文或编码串的位置，避免只截到最终值却不知道输入。
- 协议回放验证：用本地输出发真实请求，状态码、响应结构和关键字段符合预期。
- 失败归因：签名格式正确但服务端拒绝时，优先查环境指纹、会话绑定、TLS/HTTP 指纹和缺失预热。

## 踩坑记录

| # | 坑 | 现象 | 正确做法 |
| --- | --- | --- | --- |
| 1 | 直接反编译整个 VMP | 时间成本高，版本一变就失效 | 先插桩学习 I/O 和 hot path |
| 2 | 只 hook apply/call | 某些 VM 直接函数表调用，无日志 | 优先源码级插桩，hook 只作补充 |
| 3 | 过早补全浏览器环境 | 补丁越多越不稳定 | 先证明读取了哪些属性，再最小补齐 |

## 可验证事实清单

- [ ] 关键 JS、VM 入口、dispatch loop 已定位。
- [ ] 动态字段的 source -> entry -> builder -> writer -> sink 已记录。
- [ ] hot keys / hot methods / hot functions 已归档。
- [ ] 已决定纯算法、沙箱、补环境或协议恢复路线。
