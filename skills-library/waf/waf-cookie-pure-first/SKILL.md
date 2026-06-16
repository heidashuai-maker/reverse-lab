---
name: waf-cookie-pure-first
description: 用于站点 JS challenge 或 WAF 动态 cookie 复现，例如 w_tsfp、S/T、反爬 cookie、动态探针 cookie；用户想要可复用 Python 脚本时触发。优先还原纯 Python 协议/算法，纯算短时间无法完成时再退到 iv8 执行浏览器侧 JS。若没有本地 JS 文件，应先从目标页自动发现并下载动态路径下的探针脚本（如 probe.js / probev3.js），不要硬编码动态目录。不要用于仅定位 sign 入口、通用 AST 解混淆、一次性 DevTools hook 脚本或完整协议还原（涉及 WASM/GraphQL/WebSocket 等复杂链路时改用 web-protocol-recovery）。
---

# WAF Cookie 纯算优先

把动态 WAF / 反爬 cookie 还原成 Python 脚本，严格按以下优先级推进：

1. 纯 Python 计算。
2. Python + `iv8` 执行浏览器侧 JS 作为兜底。
3. **禁止使用浏览器自动化**（Playwright/Selenium/CDP），无论是否 headless。如果需要获取远程 JS 文件，使用 `webfetch` 工具下载。发现 JS 脚本路径时先用 `webfetch` 拉取，不要启动浏览器。

本 skill 基于起点 `w_tsfp` 的工作流沉淀：

```text
document.cookie writer
-> VM register holding cookie string
-> base64 payload
-> RC4-like encryption
-> JSON plaintext
-> checksum / fingerprint / timestamp validation
-> pure Python generator
```

注意：Tencent WAF 常有**两层**防护——第一层是 JS VM challenge（产 w_tsfp），第二层是 Tencent CAPTCHA（人机验证）。本 skill 只覆盖第一层的纯算还原。第二层需要用打码服务、住宅代理或浏览器自动化处理。

## 触发边界

用户需要以下结果时使用本 skill：

1. 用 Python 动态生成 WAF cookie，例如 `w_tsfp`。
2. 把 JS challenge cookie 转成纯 Python 算法。
3. 先用运行时执行证明 cookie 可用，再抽取纯算逻辑。
4. 同时产出两个版本：纯 Python 主版本，`iv8` 兜底版本。
5. 基于本地 JS challenge 文件，例如 `p3.js`，和请求样本做可用采集器。
6. 没有本地 JS 文件，但用户给了目标页，可自动发现并下载动态路径下的 `probev3.js` 等探针脚本。

以下情况不要使用本 skill：

1. 用户只想找参数生成入口。改用 `find-crypto-entry`。
2. 用户只想要 DevTools hook 脚本。改用 `browser-hook-snippets`。
3. 用户想在 Node 中运行任意浏览器 JS。改用 `env-patch`。
4. 用户明确只要紧凑 `iv8` 复现，不做纯算。改用 `iv8-web-reverse`。
5. 用户想阅读整文件 AST 解混淆结果。改用 `ast-deobfuscate`。
6. 目标明显是瑞数固定项目骨架。改用 `rs-reverse`。
7. 涉及完整协议链路还原（WASM + 签名 + 字体解码 + WebSocket/GraphQL/protobuf 等多层复合保护）。改用 `web-protocol-recovery`。

## 核心原则

除非用户只要求兜底版，否则不要停在“执行 JS 能产 cookie”。

默认最终目标：

```text
requests.Session
+ pure Python cookie generator
+ real request verification
```

兜底目标：

```text
requests.Session
+ iv8 JSContext executes local/dynamic JS
+ cookie captured from document.cookie
+ real request verification
```

## 工作流

### 1. 准备或发现 JS 材料

如果用户提供了本地 JS 文件，优先使用本地文件。

如果没有本地 JS 文件，但用户给了目标页或站点地址，先自动发现探针脚本，不要硬编码动态目录。**获取远程脚本时使用 `webfetch` 工具，不要启动浏览器自动化。** 例如同一站点同一路径下可能出现多个入口：

```text
https://www.qidian.com/C2WF946J0/probe.js
https://www.qidian.com/C2WF946J0/probev3.js
```

其中 `C2WF946J0` 可能变化，通用处理应从页面 HTML、首跳响应、脚本标签、内联 JS 或跳转/挑战响应中提取真实路径。

**不要因为文件名没有 `v3` 就判定错误。** Tencent WAF 里 `probe.js` 和 `probev3.js` 可能同时有效但处在不同阶段：首跳 `202` challenge 可能加载 `probe.js?v=...`，通过第一层后返回的业务/验证码 HTML 可能加载 `probev3.js`。应保留所有发现到的 probe 候选，分别记录来源响应和用途；优先分析实际写目标 cookie 的脚本，若用户指出真实脚本为 `probev3.js`，必须拉取并对比，而不是只沿用首跳里的 `probe.js`。

推荐发现规则：

1. 请求目标页 HTML，保留最终 URL、响应头、Set-Cookie 和正文。
2. 用正则从 HTML 中匹配 `/<dynamic>/probe(?:v3)?\.js`、`src="...probe(?:v3)?\.js?..."`、`src='...probe(?:v3)?\.js?...'`。
3. 动态目录不要写死为 `C2WF946J0`，只把它当作样例。可用模式：`/[A-Za-z0-9_-]+/probe(?:v3)?\.js`。
4. 若页面没有直接出现，检查所有外链脚本和 challenge 片段，再搜索 `probe`。
5. 下载脚本到 `js_reverse_cache/`，文件名带域名、脚本名和版本，例如 `qidian_probe.js`、`qidian_probev3.js`。
6. 后续纯算和 `iv8` 兜底使用确认过的目标脚本，并在报告中说明每个脚本的来源 URL 和响应阶段。

Python 发现逻辑可以写成独立函数：

```python
from urllib.parse import urljoin
import re

def find_probe_urls(page_url, html):
    patterns = [
        r'["\']([^"\']*probe(?:v3)?\.js(?:\?[^"\']*)?)["\']',
        r'(/[A-Za-z0-9_-]+/probe(?:v3)?\.js(?:\?[^\s"\']*)?)',
        r'(https?://[^\s"\']+/[A-Za-z0-9_-]+/probe(?:v3)?\.js(?:\?[^\s"\']*)?)',
    ]
    urls = []
    for pattern in patterns:
        for match in re.findall(pattern, html):
            candidate = match[0] if isinstance(match, tuple) else match
            if 'probe' in candidate:
                url = urljoin(page_url, candidate)
                if url not in urls:
                    urls.append(url)
    return urls
```

### 2. 证明运行时 cookie 可用

拿到 JS 后，先判断 VM 类型，再决定是否值得做运行时复现。

```text
拿到探针 JS
  ↓
搜索 __TENCENT_CHAOS_VM
  ├─ 找到 → Tencent Chaos VM：跳过 iv8 运行时，直接进入 Step 3（纯算构造）
  └─ 未找到 → 尝试 iv8 运行时复现 → 抽取算法
```

#### Tencent Chaos VM（直接跳过运行时）

Tencent WAF 的 `probe.js` 使用自定义 VM，该 VM 会检测以下环境特征来判断是否在真实浏览器中运行：

- `navigator.webdriver` 是否为 `false`
- `window.cdc`、`window.cdp` 等 Chrome DevTools Protocol 标记是否存在
- `navigator.plugins` 的 `length` 和 `item` 方法
- `canvas` 和 `webgl` 的 fingerprint API 返回值
- `constructor` 的名称（检测 `constroctor` 拼写变体）
- `document.all` 是否存在

iv8 和 Node.js `vm` 模块提供的 mock 无法通过全部检查，VM 不会产出 cookie。

**处理方式：** 直接进入 Step 3（拆分 cookie payload），因为已知 Tencent WAF 的 w_tsfp 结构为 `base64(rc4(json))`，跳过运行时验证，用纯 Python 构造 payload 后用真实请求验证。

#### 非 Chaos VM（常规 iv8 运行时）

使用 `iv8` 时优先：

1. `JSContext(environment=...)` with URL, navigator, and screen.
2. `__iv8__.page.load(...)` so scripts run in page lifecycle order.
3. A `document.cookie` setter with a real cookie jar.
4. Manual dispatch for `DOMContentLoaded`, `visibilitychange`, and `load` if the script registers listeners.
5. `eventLoop.drain()` and `eventLoop.advance(...)` for timers.

起点案例常见 patch：

```javascript
window.btoa = function(input) {
  input = String(input);
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
  let output = '', i = 0;
  while (i < input.length) {
    const c1 = input.charCodeAt(i++) & 255;
    const c2 = i < input.length ? input.charCodeAt(i++) & 255 : NaN;
    const c3 = i < input.length ? input.charCodeAt(i++) & 255 : NaN;
    output += chars[c1 >> 2]
      + chars[((c1 & 3) << 4) | (c2 >> 4)]
      + chars[Number.isNaN(c2) ? 64 : (((c2 & 15) << 2) | (c3 >> 6))]
      + chars[Number.isNaN(c3) ? 64 : (c3 & 63)];
  }
  return output;
};
```

运行时复现完成标准：

1. Captures the target cookie string.
2. Adds it to `requests.Session` cookies.
3. Real request returns the expected page/API response, not a captcha/challenge page.

### 3. 定位最终写 cookie 点

对 VM 风格 challenge，hook 最终 `document.cookie` 写入，并解析 VM 寄存器。

Tencent Chaos VM `case 14` pattern:

```javascript
e[I[++k]][e[I[++k]]] = e[I[++k]];
```

含义：

```javascript
object[property] = value
```

At a cookie write, expect:

```text
object = document
key = "cookie"
value = "target_cookie=...;expires=...;path=/"
```

如果断在 cookie setter 内部，操作数通常已经被消费。应从 `I[k - 2]`、`I[k - 1]`、`I[k]` 读，不要从 `I[k + 1]` 读。

### 4. 拆分 cookie payload

如果 cookie 值像 base64：

1. Strip `name=` and attributes.
2. Base64 decode.
3. 用候选 transform/key 解密样本 cookie，拿到 JSON 明文后逐字段对比。
4. Compare multiple samples when available.
5. Identify fixed and dynamic byte ranges.
6. Test whether shape-only randomization passes the server.

重要规则：

如果只随机动态区会返回 captcha/challenge，说明服务端校验内部算法。继续做纯算还原，不要把 shape-only 生成器作为最终版。

**样本 cookie 只能用于差分和验证，不能作为最终实现。** 如果用户给了“真实可用 cookie”，必须先解密样本，记录 `loadts`、`timestamp`、`timestamp-loadts`、`fingerprint`、`abnormal`、`checksum` 等字段，然后让生成器动态构造同形 payload。不要把样本 `w_tsfp` 原样写进最终脚本，也不要在请求前覆盖用户样本后误以为样本不可用。

### 5. 还原变换链

围绕最终 cookie 来源寄存器插桩。

重点寻找这些高价值模式：

1. `base64(binary)` or `btoa(encrypted)`.
2. RC4 PRGA pattern:

```text
i = (i + 1) % 256
j = (j + S[i]) % 256
swap(S[i], S[j])
k = S[(S[i] + S[j]) % 256]
out += char(input[n] ^ k)
```

3. RC4 KSA pattern:

```text
S = [0..255]
j = (j + S[i] + key[i % key.length]) % 256
swap(S[i], S[j])
```

4. JSON plaintext construction.
5. Checksum or digest formula, or checksum field validation behavior.

起点案例的纯算链路是一个样例，不是通用公式：

```python
checksum = md5(url + "mEVfthhorhYCfcyai8Ioe2JTEHBxovzD" + timestamp)

plain = {
    "loadts": loadts,
    "timestamp": timestamp,
    "fingerprint": "",
    "abnormal": "0" * 32,
    "checksum": checksum,
}

w_tsfp = base64(rc4("tg09It3*9h", json.dumps(plain, separators=(",", ":"))))
```

不要假设这些常量通用，必须从当前目标脚本和样本 cookie 中提取/验证。特别是 `fingerprint` 不能默认设为空，`timestamp-loadts` 不能默认设为 300ms，`checksum` 也不能默认使用某个盐公式。

**差分优先规则：** 如果用户提供了样本 `w_tsfp`，先用已确认的 RC4 key/base64 链路解密样本，再让本地生成器复现同一 payload 结构。优先比较：

1. `fingerprint` 是否为空或固定 32 位 hex。
2. `timestamp - loadts` 的固定偏移，例如样本可能是 760ms 而不是 300ms。
3. `checksum` 是真实 digest、空字符串、固定值，还是服务端不校验。
4. Base64 padding 是否保留，样本可能带 `=`，动态生成可能需要测试保留/去除两种。

**checksum 不要靠单条样本硬猜。** 若 `md5(url + salt + timestamp)` 等常见组合对不上，应做验证矩阵：正确 `fingerprint` + 不同 offset + `checksum` 为空/样本值/全 0/候选公式。以真实响应中业务数据是否出现为准。有的站点会对错误 checksum 返回短验证码页，但对 `checksum=""` 返回业务页；此时最终实现应保留经过验证的空 checksum，而不是强行套用旧盐。

**从 Tencent Chaos VM 中提取常量的方法：**

1. **定位 string table**：probe.js 末尾有 `["Promise",void 0,"apply",...]` 数组。其中的字符串按索引访问，常见索引：
   - `"key"`（通常索引 127）→ RC4 key 的名称引用，**实际 key 值**由 VM 指令流中的 `case 4`（`w[reg] += String.fromCharCode(code)`）逐字符构建
   - `"md5"` / 28 个整数常量（如 `1732584193`、`1732584194`、`1200080426`...）→ MD5 相关算法常量
   - `"timestamp"`、`"loadts"`、`"fingerprint"`、`"abnormal"`、`"checksum"` → payload 字段名

2. **Base64 解码字节码**：VM 指令流是 Base64 编码的字节码，用 probe.js 内的自定义 Base64 解码（非标准）。解码后经过 LEB128 + zigzag 解码得到指令数组。

3. **搜索 RC4 key**：在解码后的指令数组中搜索 `case 3`（赋值 `w[reg] = val`）后跟 `case 4`（追加字符）的序列，收集可打印字符。如果脚本是已知的 Tencent WAF 标准版，key 通常是 `tg09It3*9h`（可通过已解密的 payload 验证）。

4. **搜索 checksum salt**：搜索 `case 4` 构建的 32+ 字符长字符串。如果找到类似 `mEVfthhorhYCfcyai8Ioe2JTEHBxovzD` 的 32+ 字符序列，即为 checksum salt。

5. **快速验证**：用候选 key 和 salt 构造 w_tsfp，若服务端返回 200（非 202）则 key 和 salt 正确。如果只触发第二层 CAPTCHA 但还是 200，说明 key 正确但可能需要基础 cookies（见下文）。

**重要时序约束**：实际验证经常要求 `timestamp = loadts + N`（固定偏移），不能使用两个独立时间戳。不同站点可能有不同的偏移量，必须从样本或试验确定：

```python
loadts = int(time.time() * 1000)
timestamp = loadts + N  # N 来自样本差分或验证矩阵，不要硬编码为 300
```

**Base64 padding 需要实测**：默认优先测试 `base64.b64encode(...).decode().rstrip("=")`，但不要把去 padding 当成固定规则。验证矩阵必须同时测试保留 `=` 和去掉 `=` 两种输出；如果只有保留 padding 才返回业务数据，最终实现应保留 padding。本次 qidian 类目标也可能出现不同 checksum/payload 长度下 padding 行为不同的情况，因此以真实响应分类为准。

### 6. 优先构建纯 Python

创建一个干净单文件脚本，包含：

1. Editable constants at top: `PAGE_URL`, `UA`, headers, base cookies.
2. `checksum(...)` function only if当前目标验证需要；若验证表明 checksum 为空才通过，则显式写 `"checksum": ""` 并注明来源。
3. `rc4(...)` or target transform.
4. `generate_cookie_value(...)`.
5. `requests.Session` verification.

**基础 cookies 的重要性**：仅设置 `w_tsfp` cookie 是不够的。服务端会检查 session 中是否包含站点的基础 cookies（如 `e1`、`e2`、`_csrfToken`、`newstatisticUUID`、`HMACCOUNT` 等）。缺少这些 cookie 即使 w_tsfp 正确也会触发验证码。应该在最终的 Python 脚本中一并设置：

```python
BASE_COOKIES = {
    "e1": "%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A4...",
    "e2": "%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A4...",
    "_csrfToken": "uuid-value",
    "newstatisticUUID": "timestamp_random",
    "x-waf-captcha-referer": "",
    # ... 其他站点必需的 cookies
}
```

**基础 cookies 的提取流程：**

1. **首次请求获取 x-waf-captcha-referer**：先发一次不带 w_tsfp 的 GET，服务端返回 202 时会在响应头 `Set-Cookie` 中设置 `x-waf-captcha-referer`。捕获此值并在后续请求中原样带回。

2. **从浏览器 DevTools 导出**：用真实浏览器正常访问目标站一次，在 DevTools > Application > Cookies 中导出所有 cookie。重点关注：
   - `e1`、`e2` — 站点跟踪标识（URL 编码的 JSON）
   - `_csrfToken` — 反 CSRF token（UUID 格式）
   - `newstatisticUUID` — 会话标识（`时间戳_随机数` 格式）
   - `fu` — 用户标识（数字）
   - `HMACCOUNT`、`Hm_lvt_*`、`Hm_lpvt_*` — 分析/统计 cookie

3. **URL 编码处理**：`e1`、`e2` 等 cookie 值通常是 URL 编码的 JSON，直接从 DevTools 复制即可，Python 的 `requests` 会自动处理。

4. **cookie 时效**：`_csrfToken`、`newstatisticUUID`、`HMACCOUNT` 等通常是长期有效的（天级到月级），不需要每次请求都刷新。`x-waf-captcha-referer` 每次从 202 响应获取即可。

**`timestamp = loadts + N` 约束**：验证时保证 `timestamp - loadts` 为固定值（如 300ms、760ms），不要产生两个独立毫秒时间戳：

```python
loadts = int(time.time() * 1000)
timestamp = loadts + N  # 固定偏移，具体值通过样本或试验确定
```

**Base64 padding**: 最终是否去掉 `=` padding 由验证矩阵决定。实现中可提供 `strip_padding` 开关；默认可先用 `rstrip("=")`，但如果真实请求只有保留 padding 才成功，必须保留 `=`。

为兼容 JavaScript RC4 行为，对字符使用 `ord(ch) & 255`，加密输出先按 Latin-1 编码再 base64：

```python
def js_rc4(key, text):
    s = list(range(256))
    j = 0
    key_codes = [ord(ch) & 255 for ch in key]
    for i in range(256):
        j = (j + s[i] + key_codes[i % len(key_codes)]) & 255
        s[i], s[j] = s[j], s[i]

    i = j = 0
    out = []
    for ch in text:
        i = (i + 1) & 255
        j = (j + s[i]) & 255
        s[i], s[j] = s[j], s[i]
        k = s[(s[i] + s[j]) & 255]
        out.append(chr((ord(ch) & 255) ^ k))
    return "".join(out)
```

### 7. 最后才构建 iv8 兜底

满足以下情况再构建兜底版：

1. The checksum or transform remains opaque after a reasonable trace pass.
2. The output depends heavily on browser fingerprint APIs.
3. The target uses wasm/native browser APIs that are not worth porting.
4. The user needs a working script quickly.

兜底脚本规则：

1. Use `utils/iv8_silent.py` and `utils/logger.py` helpers if the project already has them.
2. Save dynamic materials under `js_reverse_cache/`.
3. Keep the same `requests.Session` for cookie generation and request replay.
4. Print the final cookie and the real response status/body.

## 输出文件

没有项目命名约定时，优先使用：

```text
<site>_pure_final.py          # primary deliverable
<site>_dynamic_cookie_iv8.py  # fallback deliverable
utils/iv8_silent.py           # fallback helper
utils/logger.py               # fallback helper
js_reverse_cache/             # temporary dynamic materials only
```

用户要求清理项目时，仅保留：

```text
source JS needed by fallback
pure final script
iv8 fallback script
utils/
```

删除 trace 脚本、探测脚本、反汇编 dump、DOM dump 和缓存目录，除非用户要求保留证据。

## 完成标准

纯算版满足以下条件才算完成：

1. It does not import `iv8` or execute the target JS.
2. It generates the cookie directly in Python.
3. A real request with the generated cookie returns the expected business page/API, not only the first-layer JS VM challenge (probe.js/probev3.js).

注意：有些站点（如 qidian.com）的 Tencent WAF 有两层——第一层是 JS VM challenge（产 w_tsfp），第二层是 Tencent CAPTCHA。纯算版只负责第一层的 w_tsfp 生成。

**响应分类不能只看脚本名。** 业务页里也可能常驻加载 `TCaptcha.js` 或 `probev3.js`，因此不能仅凭 HTML 中包含 `TCaptcha.js`、`captcha.qq.com`、`turing.captcha.qcloud.com` 就判定失败。必须同时检查业务内容标记、响应长度、状态码、首跳 challenge 特征和用户给的可用样本输出。推荐分类：

1. `first-layer challenge`: 202 或短 HTML，只包含 probe 入口，没有业务内容。
2. `business page with captcha assets`: 200，包含业务列表/API 数据，同时可能包含 `TCaptcha.js`/`probev3.js`。
3. `captcha wall`: 200，短页面或明确只有验证码容器，没有业务内容。

如果请求返回 200 且有业务数据，即使页面包含验证码脚本，也应报告 `pure: success`，不要误报为 `success (layer 1)` 或 failed。

兜底版满足以下条件才算完成：

1. It executes the target JS in `iv8`, not browser automation.
2. It captures the cookie via `document.cookie` or equivalent runtime state.
3. A real request succeeds.

明确报告两个状态：

```text
pure: success | success (layer 1) | partial | failed
fallback: success | not needed | success as backup
verified request: status + response type
```
