# 案例：WASM helper 协议恢复骨架

> 难度：★★★★☆
> 反爬类型：签名型 / 响应解密型 / 混合型
> 首选路线：`find-crypto-entry` 定位入口，必要时交给 `web-protocol-recovery` 做端到端纯协议恢复
> 复现形态：Python+WASM helper / Node.js+WASM helper / 纯 Python 移植
> 最后验证日期：待填

## 适用范围

适用于目标把 sign、token、请求体加密、响应解密、protobuf 包装、字体/二进制解码等核心逻辑放进 `.wasm`，JS 侧只负责 glue、memory 写入、导出函数调用和请求发送的场景。

不适用于普通 JS 混淆、JSVMP 字节码虚拟机、仅 WebCrypto 调用且无 WASM 的场景。

## 技术指纹

### 资源与 JS 特征

- [ ] 网络请求中存在 `.wasm`，或 JS 中出现 `WebAssembly.instantiate` / `WebAssembly.instantiateStreaming`。
- [ ] JS glue 中出现 `WebAssembly.Memory`、`exports`、`instance.exports`、`memory.buffer`。
- [ ] 出现 `wasm-bindgen` / `__wbindgen` / `wasm-pack` / `Emscripten` / `Module.cwrap` / `Module.ccall`。
- [ ] JS 侧只暴露包装函数，核心算法不可读或只有内存读写痕迹。

### 参数与请求特征

- [ ] 请求中存在固定长度 sign/token/header，值随 URL、body、时间或 nonce 变化。
- [ ] 请求前有预热接口，下发 seed、salt、session、wasm URL 或版本号。
- [ ] 响应 body 是二进制、Base64、protobuf、gzip 后再加密，JS 侧调用 WASM 解密。

## 参数特征（快速路由）

| 参数 / 字段 | 位置 | 长度 / 字符集 | 生成时机 | 判定价值 |
| --- | --- | --- | --- | --- |
| `sign` / `signature` / `x-sign` | URL query / header / body | 32/64 hex、Base64、固定长度自定义串 | WASM export 调用后生成 | 中 |
| `token` / `x-token` | URL query / header | 长 token，可能会话绑定 | 预热接口或 WASM 调用后生成 | 中 |
| 加密 request body | body | 二进制、Base64、protobuf-like | 写入 WASM memory 后输出 | 高 |
| 加密 response body | response body | ArrayBuffer、Base64、protobuf、gzip 后密文 | fetch 返回后交给 WASM decode | 高 |
| `wasm` 版本号 / seed / salt | boot config / preflight response | 字符串或数字 | WASM 初始化前下发 | 高 |

高置信度组合：动态参数或加密 body + `.wasm` 资源 + `WebAssembly.Memory` / `instance.exports` / glue memory read-write。只有普通 `sign` 参数名不足以命中 WASM case。

## 指纹检测规则

```text
快速检测：
1. 搜索 WebAssembly.instantiate / instantiateStreaming / WebAssembly.Memory。
2. 列出网络中的 .wasm 资源，保存到 targets/<site>/source/。
3. 搜索 instance.exports / exports.sign / exports.encrypt / exports.decrypt / cwrap / ccall。
4. 对业务请求做一次 hook，记录 sign/token/header 写入前后的输入输出。

高置信度：
- .wasm 资源存在；
- 动态字段由 JS glue 调用 wasm export 后生成；
- 改 URL/body/时间后输出随之变化。
```

## 已验证定位路径

```text
步骤 1：抓网络，定位 .wasm 与 glue JS。
步骤 2：保存原始 .wasm、glue JS、关键请求样本到 targets/<site>/。
步骤 3：hook WebAssembly.instantiate / instantiateStreaming，记录 imports、exports、memory。
步骤 4：hook exports 上的候选函数，记录参数、返回值、调用栈。
步骤 5：hook memory 写入/读取边界，确认明文输入和密文/签名输出位置。
步骤 6：用固定输入重放，确认输出是否稳定。
步骤 7：选择复现路线：直接调用 WASM、移植算法、或保留极小 WASM helper。
步骤 8：用真实业务请求做协议回放验收。
```

## Phase 处理流程

### Phase 1：WASM 资源确认

```text
1. 抓网络并保存 .wasm、glue JS、Worker JS。
2. 记录 instantiate / instantiateStreaming 调用栈。
3. 记录 imports、exports、memory 是否存在。
```

### Phase 2：入口与 memory 协议

```text
1. hook exports 候选函数，记录参数和返回值。
2. hook glue 的字符串/ArrayBuffer 写入函数。
3. 确认返回值是 pointer、length、状态码还是结构体地址。
```

### Phase 3：本地 WASM helper

```text
1. 固定 imports，避免补无关浏览器环境。
2. 用固定输入调用同一 export。
3. 对齐 memory 写入、endianness、字符串编码和输出读取方式。
```

### Phase 4：协议回放

```text
1. 用本地输出替换浏览器输出发真实请求。
2. 分别测试 URL/body/time/nonce/cookie 对输出的影响。
3. 记录不能脱离浏览器的原因，如果必须保留浏览器兜底。
```

## 链路图

```text
source: upstream config / url / query / body / timestamp / nonce / cookie
entry: JS glue wrapper or wasm export
builder: memory write + export call + memory read
writer: URL param / header / encrypted body / response decoder
sink: fetch / XHR / requests / http client
verification: browser output == local output, protocol replay returns expected data
```

## 还原代码模板

### Node.js 直接调用 WASM

```javascript
const fs = require("fs");

async function loadWasm(path, imports = {}) {
  const bytes = fs.readFileSync(path);
  const { instance } = await WebAssembly.instantiate(bytes, imports);
  return instance;
}

async function genSign(input) {
  const instance = await loadWasm("./source/target.wasm", {
    env: {
      // 按实际 imports 补最小函数，不要补整套浏览器环境。
    },
  });

  const { memory, sign } = instance.exports;
  const view = new Uint8Array(memory.buffer);

  // TODO: 按 glue JS 的写入规则分配 offset 并写入 input。
  const ptr = 0;
  const bytes = Buffer.from(input, "utf8");
  view.set(bytes, ptr);

  const outPtr = sign(ptr, bytes.length);

  // TODO: 按返回协议读取 length / pointer / null-terminated string。
  return readString(view, outPtr);
}

function readString(view, ptr) {
  let end = ptr;
  while (view[end] !== 0) end += 1;
  return Buffer.from(view.slice(ptr, end)).toString("utf8");
}
```

### Python 调用 WASM helper

```python
# 可按项目依赖选择 wasmtime / wasmer / pyodide-node bridge。
# 保留 WASM helper 时，重点是固定 imports、memory I/O 和验收样本。

def gen_sign(payload: dict) -> str:
    raise NotImplementedError("fill with verified wasm invocation")
```

## 验证方法

- 固定输入样本：同一 URL、body、timestamp、nonce 下，浏览器和本地输出完全一致。
- 变化样本：分别改变 URL、body、timestamp、nonce，确认输出变化维度一致。
- 协议验收：用本地输出发真实请求，响应结构、状态码和关键字段符合预期。
- 失败归因：浏览器输出可用、本地输出不可用时，优先检查 memory I/O、imports、endianness、编码、时间/随机数和会话绑定。

## 踩坑记录

| # | 坑 | 现象 | 正确做法 |
| --- | --- | --- | --- |
| 1 | 只看 export 名称就猜入口 | `sign` 名称可能是 wrapper 或 dead export | hook 实际调用栈和请求前后输出 |
| 2 | 忽略 memory 协议 | 函数返回数字但不知道是 ptr、len 还是状态码 | 反查 glue JS 的 read/write helper |
| 3 | imports 补太多 | 本地可跑但引入不稳定行为 | 只补实际读取的 imports，并记录证据 |
| 4 | 忽略会话绑定 | 固定样本通过，真实请求失败 | 把 seed、cookie、预热响应纳入输入链路 |
| 5 | 直接浏览器自动化交付 | 能跑但不可移植 | 先尝试 WASM helper 或纯协议回放，自动化只作兜底 |

## 变体说明

| 变体 | 差异点 | 调整策略 |
| --- | --- | --- |
| wasm-bindgen | glue 中有 `__wbindgen_*` 辅助函数 | 复用 glue 的字符串/对象堆管理逻辑 |
| Emscripten | `Module.cwrap` / `ccall` 包装导出 | 找 cwrap 函数名和参数类型 |
| Streaming compile | WASM 不落地，直接 instantiateStreaming | hook instantiateStreaming 并保存响应 bytes |
| Worker 内 WASM | 主线程只 postMessage | hook Worker、MessageChannel、postMessage |
| 响应解密型 | 请求无 sign，响应进 WASM decode | hook fetch response.arrayBuffer/text 与 decode export |

## 可验证事实清单

- [ ] `.wasm` URL、版本和加载顺序已记录。
- [ ] glue JS 中的入口 wrapper、memory write、memory read 已定位。
- [ ] export 候选函数的入参、返回值、调用栈已记录。
- [ ] 固定输入的 browser-vs-local 输出一致。
- [ ] 真实协议回放通过，且不依赖完整浏览器自动化。
