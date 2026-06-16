# kad.arbitr.ru WASM cookie 逆向记录

## 项目用途判断

当前 `reverse-lab` 是一个 Web/JS 协议恢复工作区，主要用于把浏览器里的动态验证、签名、WASM、cookie、请求封装等链路还原成可在浏览器外运行的脚本。项目约定把每个目标放在 `targets/<source-name>/`，原始素材进 `source/`，探针和复现脚本进 `scripts/`，请求样本进 `samples/`，最终可运行程序进 `output/`。

本目标目录为 `targets/ru_sf_wasm/`，用于记录 `https://kad.arbitr.ru/` 的 `pr_fp` 和 `wasm` cookie 生成链路，以及非浏览器请求验证。

## 目标与现象

- 目标站点：`https://kad.arbitr.ru/`
- 保护形态：`ddos-guard` + 页面内 `Pravocaptcha` / WASM 指纹 cookie。
- 关键 cookie：
  - `pr_fp`：由 `/Content/Static/js/common/fp.js` 加载 `fp_bg.wasm` 后生成。
  - `wasm`：由 `/Wasm/api/v1/wasm.js` 加载 `wasm_bg.wasm` 后生成，`max-age=450`。
- 触发时机：搜索或进入业务详情前会执行 `Common.executePravocaptcha`，先补 `pr_fp`，再补 `wasm`，然后请求验证码判定接口。

## 素材与来源

已保存的原始素材：

- `source/home.html`：初始页面响应。
- `source/full.html`：Full 模式页面响应。
- `source/layout.202605261437.js`：全局配置与公共逻辑。
- `source/kad.202605261437.js`：业务搜索与 `Pravocaptcha` 调用逻辑。
- `source/fp.js`、`source/fp_bg.wasm`：`pr_fp` 生成逻辑。
- `source/wasm.js`、`source/wasm_bg.wasm`：`wasm` 生成逻辑。

请求和验证样本保存在 `samples/`，其中 `browser_cookie_probe.json` 是浏览器侦察结果，`search_force_451.html` 是无验证码 token 强制搜索返回的 451 页面。

## 关键链路

页面配置位于 `layout.202605261437.js`：

- `getInstances` -> `/Kad/SearchInstances`
- `checkIsNeedShowCaptcha` -> `/Recaptcha/IsNeedShowCaptcha`
- `getCaptchaWasm` -> `/Wasm/api/v1/wasm.js`
- `getCaptchaWasmBG` -> `/Wasm/api/v1/wasm_bg.wasm`

业务逻辑位于 `kad.202605261437.js`：

1. `Pravocaptcha.prototype.initializeFp()` 加载 `fp.js` 和 `fp_bg.wasm`，调用 `window.fp.get()`。
2. `fp_bg.wasm` 通过 JS glue 的 `set_cookie` 写入 `pr_fp=...; domain=.arbitr.ru; samesite=none; secure`。
3. 如果没有 `$.cookie("wasm")`，则 `Pravocaptcha.prototype.loadWasm()` 加载 `wasm.js` 和 `wasm_bg.wasm`。
4. 本地复现中需要显式调用 `wasm.main()`，它写入 `wasm=...; max-age=450; domain=.arbitr.ru; path=/; samesite=none; secure`。
5. cookie 准备完成后，请求 `/Recaptcha/IsNeedShowCaptcha` 判断是否还需要验证码。
6. 搜索接口 `/Kad/SearchInstances` 会在有 token 时带 `RecaptchaToken` 请求头；无 token 且服务端判定需要验证码时，会返回 451。

## 离线复现方案

实现文件：

- `scripts/generate_cookies.js`
  - 在独立 Node 进程中搭建最小浏览器环境桩。
  - 加载本地 `fp.js/fp_bg.wasm` 和 `wasm.js/wasm_bg.wasm`。
  - 输出 JSON：`pr_fp`、`wasm`、`cookieHeader`、`userAgent`。
  - 不依赖浏览器、Playwright、Selenium 或真实 `document/window`。

- `output/kad_request.py`
  - 使用 `curl_cffi` 创建 Chrome TLS 指纹会话。
  - 先访问 `/Version/Change?mode=Full&returnUrl=/` 建立站点会话和 `ddos-guard` cookie。
  - 调用 Node helper 生成 `pr_fp/wasm` 并注入会话 cookie。
  - 请求 `/Recaptcha/IsNeedShowCaptcha` 验证 cookie gate。
  - 可选传入 `--case-number` 调用 `/Kad/SearchInstances`；如果服务端返回需要验证码且没有 `--recaptcha-token`，默认跳过搜索，避免重复触发 451。
  - 支持 `--captcha-image` 保存验证码图片，`--interactive-captcha` 在同一会话内保存图片并提示输入验证码，校验成功后用 captcha id 作为 `RecaptchaToken` 继续搜索。

## 验证结果

本地 cookie helper：

```text
node targets\ru_sf_wasm\scripts\generate_cookies.js --pretty
```

输出包含：

- `pr_fp=b2585530343fa4f007a70972f6b0a5a9d2412302d7f9970d8fb547564bb3f897`
- `wasm=d26b7c65fcc34ab72bdb5a05dce32b45`

其中 `wasm` 与用户提供样例 `d26b...2b45` 一致。

默认非浏览器请求：

```text
python targets\ru_sf_wasm\output\kad_request.py
```

验证结果：

- bootstrap 页面：HTTP 200。
- `/Recaptcha/IsNeedShowCaptcha`：HTTP 200，`content-type=application/json; charset=utf-8`。
- 当前返回：`{"Result": true, "Message": "", "Success": true, ...}`。

带案号但不带验证码 token：

```text
python targets\ru_sf_wasm\output\kad_request.py --case-number "А40-60483/2023"
```

脚本安全跳过搜索，原因是验证码判定接口返回 `Result=true`。

强制搜索证据：

```text
python targets\ru_sf_wasm\output\kad_request.py --case-number "А40-60483/2023" --force-search --save-response targets\ru_sf_wasm\samples\search_force_451.html
```

结果：`/Kad/SearchInstances` 返回 HTTP 451，原始 HTML 已保存到 `samples/search_force_451.html`。

验证码取图证据：

```text
python targets\ru_sf_wasm\output\kad_request.py --case-number "А40-60483/2023" --captcha-image targets\ru_sf_wasm\samples\captcha_latest.png
```

结果：`/Recaptcha/GetCaptchaId` 返回 HTTP 200 JSON，`/Recaptcha/GetImage/<id>` 返回 HTTP 200 `image/jpeg`，图片已保存到 `samples/captcha_latest.png`。

## DDoS-Guard 挑战页识别

如果响应体出现以下特征，说明请求被最外层 DDoS-Guard 拦截，还没有进入 `kad.arbitr.ru` 页面逻辑、`pr_fp/wasm` 逻辑或业务验证码逻辑：

```html
<title>DDoS-Guard</title>
<script src="https://check.ddos-guard.net/check.js"></script>
<script defer="defer" src="/.well-known/ddos-guard/js-challenge/index.js"></script>
```

对应页面通常包含：

- `/.well-known/ddos-guard/js-challenge/index.css`
- `/.well-known/ddos-guard/js-challenge/view.js`
- `/.well-known/ddos-guard/js-challenge/index.js`
- `data-ddg-origin="true"`
- 文案 `Checking your browser before accessing ...`

这类响应不是业务接口 403/451，也不是 Pravocaptcha 的 `pr_fp/wasm` 问题。它表示链路卡在第一层：

```text
DDoS-Guard 外层防护
  -> 站点会话和页面脚本
    -> pr_fp / wasm cookie
      -> /Recaptcha/IsNeedShowCaptcha
        -> /Kad/SearchInstances
```

排查时先看 bootstrap 响应。如果 `bootstrap.text_preview` 里有 `DDoS-Guard` 或 `/.well-known/ddos-guard/js-challenge/`，应优先处理 `__ddg*` 会话，而不是继续排查 `pr_fp`、`wasm` 或 `RecaptchaToken`。

已修正点：`DEFAULT_UA` 与 `curl_cffi` 的 `impersonate` 已统一到 Chrome 120 / `chrome120`。同时 `scripts/generate_cookies.js` 中的 `UAParser` stub 已改为从传入 UA 派生 Chrome 主版本，避免出现“请求头 Chrome 120，但 JS 环境返回 Chrome/Blink 125”的不一致。

维护建议：

- `DEFAULT_UA` 和 `curl_cffi` 的 `impersonate` 应保持同一 Chrome 主版本。
- Node helper 生成 `pr_fp/wasm` 使用的 UA，应与 Python 请求会话的 UA 一致。
- 如果切换 UA，也要同步更新 `generate_cookies.js --ua`、`KadClient(user_agent=...)` 和 `curl_cffi` impersonate。
- 出现 DDoS-Guard challenge HTML 时，先重新建立首页/Full 模式会话，确认 `__ddg1_`、`__ddg8_`、`__ddg9_`、`__ddg10_` 都存在且未过期。

## DDoS-Guard cookie provenance 复查

2026-06-12 通过浏览器实际观测到的 DDoS-Guard challenge 链路：

```text
GET /Version/Change?mode=Full&returnUrl=%2F  -> 403 DDoS-Guard HTML
GET /.well-known/ddos-guard/js-challenge/index.css
GET /.well-known/ddos-guard/js-challenge/view.js
GET /.well-known/ddos-guard/js-challenge/index.js
GET https://check.ddos-guard.net/check.js    -> response header etag/challenge id
GET /.well-known/ddos-guard/id/<id>           -> sets __ddg2_ on arbitr.ru
GET https://check.ddos-guard.net/set/id/<id> -> sets __ddg2 on check.ddos-guard.net
POST /.well-known/ddos-guard/mark/            -> browser fingerprint payload
POST /.well-known/ddos-guard/mark/            -> second mark request
GET /Version/Change?...                       -> 302 /
```

保存的证据：

- `samples/browser_ddg_network_20260612.txt`
- `samples/browser_ddg_req_08_mark_body.txt`
- `samples/browser_cookie_after_ddg_20260612.json`
- `samples/browser_isneed_after_ddg_20260612.json`
- `source/ddg_index.js`
- `source/ddg_check.js`

`__ddg9_` 的值与当前出口 IP 一致。本轮 Python 和浏览器在同一代理下均为 `103.151.173.91`，因此它应记录 DDoS-Guard 看到的出口 IP。之前切换过代理时，如果复用旧 cookie，`__ddg9_` 会与当前出口不一致，应视为高风险状态并重新建会话。

当前 Python baseline 已可拿到：

```text
__ddg1_
__ddg8_
__ddg9_
__ddg10_
CUID
ASP.NET_SessionId
SiteVersion
```

启用 `output/kad_request.py --ddg-replay` 后，Python 可以复现 `check.js -> id -> set/id`，并补到：

```text
__ddg2_
```

但 `/mark/` 两次返回 HTTP 400，未补到 `__ddgid_`、`__ddgmark_`、`__ddg5_`、`ddg_last_challenge` 等 challenge mark 分支 cookie。原因不是单纯少请求 `id/set/id`，而是 `source/ddg_index.js` 的 `check()` 实际逻辑为：

```text
FingerprintJS/newFp 采集
  -> fetch("/.well-known/ddos-guard/mark/", body=JSON.stringify(...))
  -> wsCheck(): WebSocket("/.well-known/ddos-guard/mark/ws")
       服务端下发 JS code
       浏览器 eval(JSCode)
       等待 window.DDG
       ws.send(JSON.stringify(responses))
```

也就是说，`mark/` 不是一个可用旧 JSON body 独立回放的普通 POST。它与同一轮 WebSocket 校验和真实浏览器 fingerprint runtime 绑定。当前用 `websocket-client` 和 `curl_cffi.Session.ws_connect()` 直连 `wss://kad.arbitr.ru/.well-known/ddos-guard/mark/ws` 均返回 400，说明服务端没有接受当前 Python 会话进入完整 mark/ws 校验阶段，或者还缺少真实 challenge 会话状态。

重要结论：`/Recaptcha/IsNeedShowCaptcha` 返回 `{"Result":true}` 不能直接归因于缺少 `__ddgid_`、`__ddgmark_`、`__ddg5_`。同一浏览器通过 DDoS-Guard 后，用页面内 `fetch("/Recaptcha/IsNeedShowCaptcha")` 实测也返回 `Result=true`。因此 `Result=true` 更像是 DDoS 外层通过之后的业务验证码判定，即 Pravocaptcha/站点风控层仍要求图形验证码；它与 DDoS-Guard 外层 cookie 不是同一个 gate。

## 结论

`pr_fp` 和 `wasm` cookie 的本地生成链路已经恢复，且可在浏览器外稳定运行。Python 请求脚本可以完成会话初始化、注入 WASM/FP cookie，并让 `/Recaptcha/IsNeedShowCaptcha` 从拦截 HTML 变为 JSON 响应。

验证码 token 链路已经按前端行为接入到脚本中：`/Recaptcha/CheckCaptcha` 成功后，前端实际传给 `/Kad/SearchInstances` 的 `RecaptchaToken` 是 captcha id。当前没有自动识别验证码；完整搜索回放可以走 `--interactive-captcha` 手动输入，或后续接入 OCR/打码服务。

## 2026-06-12 重新判断：`wasm` / `pr_fp`

本节以 `targets/ru_sf_wasm/output/test01.py` 的现象为准，修正前面“本地 cookie helper 已稳定通过 gate”的判断：当前 `scripts/generate_cookies.js` 能生成 `pr_fp/wasm`，但其中 `wasm=d26b7c65fcc34ab72bdb5a05dce32b45` 已被详情页验证为无效，不能当作最终可用链路。

### 固定输入验证

同一目标：

```text
https://kad.arbitr.ru/Card/566bf0a7-8ccc-4aef-9b45-a46be35197bf
```

同一普通 `requests` 请求方式和同一 `test01.py` socks 代理下，对比结果如下：

```text
browser_pair_from_test01:
  pr_fp=cad4977527571dd06fd0afab97842b10fce61f0bc57226d8faf6c4cb5cfb327e
  wasm=30e46614927197eaefcd402d99270b88
  result: HTTP 200, title=А88-435/2026, classification=case_card_html

helper_pair:
  pr_fp=d14d4be92de106402a7d3a5f4843f9b98e7f142311cba3886465b42ae9ce2333
  wasm=d26b7c65fcc34ab72bdb5a05dce32b45
  result: HTTP 451, title=Доступ заблокирован, classification=blocked_451
```

已保存的响应证据：

- `samples/browser_pair_from_test01_card_response.html`
- `samples/helper_pair_commented_in_test01_card_response.html`
- `samples/cross_browser_pr_helper_wasm_card_response.html`
- `samples/cross_helper_pr_browser_wasm_card_response.html`
- `samples/random_pr_browser_wasm_card_response.html`
- `samples/no_cookies_card_response.html`

交叉验证结论：

```text
browser_pr + helper_wasm  -> 451 blocked
helper_pr  + browser_wasm -> 200 case_card_html
random_pr  + browser_wasm -> 451 blocked
no cookies / only one cookie -> 200 pravocaptcha_gate, not case detail
```

因此更精确的判断是：

1. `pr_fp` 不能是随机值，随机 `pr_fp` 即使配合浏览器 `wasm` 也会 451。
2. 当前 helper 生成的 `pr_fp=d14...` 在详情页验证中可以配合浏览器 `wasm=30e...` 返回正常详情页。
3. 当前真正导致 `kad_request.py` 默认输出被 451 的主要阻塞点是 `wasm=d26...`，不是 UA、出口 IP、`curl_cffi`、`requests` 或 `__ddg1_`。
4. `wasm` 正确后，`/Recaptcha/IsNeedShowCaptcha` 也从 `Result=true` 变成 `Result=false`。验证命令：

```text
python targets\ru_sf_wasm\output\kad_request.py --probe-card --proxy socks5h://10.86.10.212:8204 --wasm 30e46614927197eaefcd402d99270b88
```

该命令保留 helper 生成的 `pr_fp=d14...`，只覆盖 `wasm`，实测返回：

```text
validationCookies.generated_wasm = d26b7c65fcc34ab72bdb5a05dce32b45
validationCookies.applied_wasm   = 30e46614927197eaefcd402d99270b88
captchaGate.json.Result          = false
cardProbe.status_code            = 200
cardProbe.text_preview title     = А88-435/2026
```

### `wasm=d26...` 无效的原因判断

`source/wasm_bg.wasm` 的字符串和 `source/wasm.js` 的导入面显示，`wasm` 不是普通常量，也不是只依赖 UA。它会读取并组合大量浏览器环境与自动化检测项，包括：

```text
webdriver / webDriverValue / navigatorPrototype
PHANTOM_* / HEADCHR_* / SELENIUM_* / nightmare / sequentum
plugins / mimeTypes / permissions / mediaDevices
screen / screenDesc / devicePixelRatio / window outer-inner dimensions
chrome properties / iframeChrome / debugTool
errorsGenerated / resOverflow / WebSocket error
battery / deviceMemory / accelerometerUsed
tpCanvas / canvas / webgl / audioCodecs / videoCodecs
```

当前 `generate_cookies.js` 用 Node stub 搭了一个“能跑 wasm”的环境，但这个环境并不像真实 Chrome：

- `navigator`、`screen`、`Window`、`Document` 等是普通 JS stub，不是原生对象和原生 prototype/descriptor。
- `plugins` / `mimeTypes` 为空数组，和真实 Chrome 暴露面不一致。
- `WebSocketStub` 抛出的错误文本、错误类型和真实 Chrome 的 `new WebSocket("itsgonnafail")` 不一致。
- `canvas` / `Image` / `tpCanvas` 返回的是固定假数据。
- `window.chrome.*` 用普通对象补出来，constructor / descriptor / iframe 行为与真实 Chrome 不一致。

这些差异会被 `wasm_bg.wasm` 编码进最终 `wasm` cookie，导致本地 helper 稳定生成一个“自洽但明显是 stub 环境”的值 `d26...`。服务端在详情页或 Pravocaptcha gate 上会识别该值并返回 451。

### 代码修正

`output/kad_request.py` 已增加：

- `--proxy`：对齐 `test01.py` 的 socks 代理或切换代理。
- `--pr-fp` / `--wasm`：覆盖 helper 生成值，区分 generated 与 applied。
- `--probe-card` / `--card-id`：请求详情页并分类响应。
- `classify_card_response()`：区分 `case_card_html`、`blocked_451`、`pravocaptcha_gate`、`ddos_guard_challenge`。

离线分类自检：

```text
browser_pair -> case_card_html
helper_pair  -> blocked_451
no_cookies   -> pravocaptcha_gate
```

后续真正要修的是 `wasm` helper：要么把 `wasm.js` 的导入结果补到接近真实 Chrome，要么先从浏览器采集一份可复用的 fingerprint profile，再让 Node helper 按该 profile 输出同类 `wasm`。在这一步完成前，不应再把 `generate_cookies.js` 的 `wasm=d26...` 视为可交付结果。

## 2026-06-12 可用 cookie 获取链路修复

已新增 `scripts/capture_browser_cookies.py`，用于获取真正可用的 `pr_fp/wasm`：

1. 启动本机 Chrome/Edge 的隔离 profile，并通过 CDP 控制。
2. 使用 `--disable-blink-features=AutomationControlled`，并通过 `Network.setUserAgentOverride` 设为普通 Chrome UA。
3. 进入 `https://kad.arbitr.ru/` 原站上下文。
4. 在真实浏览器中加载站点自己的：
   - `/Content/Static/js/common/fp.js`
   - `/Content/Static/js/common/fp_bg.wasm`
   - `/Wasm/api/v1/wasm.js`
   - `/Wasm/api/v1/wasm_bg.wasm`
5. 调用 `fp.default(...) -> fp.get()` 和 `wasm.default(...) -> wasm.main()`，由真实 Chrome 环境写入 cookie。
6. 立刻用普通 `requests` 带这两个 cookie 请求 `/Card/<id>` 做验证。

可直接运行：

```text
python targets\ru_sf_wasm\scripts\capture_browser_cookies.py --headless
```

成功输出样例：

```text
pr_fp=a395c3361242fe6fce7a9962dfc6eedd572312ac2d77d6238c7f89448ac6cb6b
wasm=284326ea091960c7af75c473c632f194
requestValidation.status_code=200
requestValidation.classification=case_card_html
```

采集结果会写入：

```text
samples/browser_generated_cookies_latest.json
```

`output/kad_request.py` 已接入该链路：

```text
python targets\ru_sf_wasm\output\kad_request.py --browser-cookies --probe-card
```

实测结果：

```text
validationCookies.generated_pr_fp=a395c3361242fe6fce7a9962dfc6eedd572312ac2d77d6238c7f89448ac6cb6b
validationCookies.generated_wasm=284326ea091960c7af75c473c632f194
captchaGate.json.Result=false
cardProbe.status_code=200
cardProbe.classification=case_card_html
```

`output/test01.py` 已改为读取 `samples/browser_generated_cookies_latest.json` 中的最新真实 Chrome cookie；如果该文件不存在或超过 420 秒，会自动调用 `capture_browser_cookies.py --headless` 刷新。它仍然使用普通 `requests` 和随机 UA 验证详情页。

实测：

```text
python targets\ru_sf_wasm\output\test01.py

status_code: 200
classification: case_card_html
title: А88-435/2026
cookies: {"wasm": "284326ea091960c7af75c473c632f194", "pr_fp": "a395c3361242fe6fce7a9962dfc6eedd572312ac2d77d6238c7f89448ac6cb6b"}
response_saved_to: targets\ru_sf_wasm\samples\test01_latest_response.html
```

当前状态：已经能稳定获取可用的两个 cookie，并在 `test01.py` 的普通 `requests` 链路中验证通过。严格意义上，这仍然是“真实 Chrome 采集 cookie + Python 复用”的过渡方案；还不是纯 Node stub 复现 `wasm`。若后续要彻底去浏览器，需要继续把真实 Chrome 的 `wasm` 输入 profile 迁回 `generate_cookies.js`。

## 2026-06-12 Node 模拟浏览器环境实验

本轮把“真实 Chrome/CDP 获取 cookie”调整为最后兜底方案，优先尝试继续修复 `scripts/generate_cookies.js` 的 Node 环境模拟。

已对齐或补强的环境面：

- `navigator` 改为原型 getter 结构，`Object.getOwnPropertyNames(navigator)` 为空，`Navigator.prototype` 顺序按真实 Chrome 149 headless 画像补齐。
- `screen` 改为原型 getter，宽高与真实采集一致：`screen=800x600`，`innerWidth=1349`，`innerHeight=749`，`outerWidth=1365`，`outerHeight=900`，`screenX=10`。
- 补齐 Chrome PDF 插件：`navigator.plugins.length=5`，`navigator.mimeTypes.length=2`。
- 补齐 `mediaDevices.enumerateDevices()`、音视频 `canPlayType()`、`matchMedia("(min-width: 1348px)")`、`tpCanvas` 透明像素、WebGL vendor/renderer/extensions。
- 修正 `window.chrome`：真实当前上下文只有 `loadTimes/csi/app`，没有 `webstore/runtime`；`detailChrome` 路径保持与浏览器 trace 一致。
- 修正 `new WebSocket("itsgonnafail")`：真实 Chrome 不同步抛错，Node stub 也不再同步抛错。
- 增加 `Function.prototype.toString` 伪原生层，getter、构造器、`setTimeout`、`matchMedia` 等暴露为 `function xxx() { [native code] }`。
- 对 `wasm.js` 的 `resOverflow` import 做运行时窄 patch，固定为真实 Chrome trace 的 `{depth:8850,errorMessage:"Maximum call stack size exceeded",errorName:"RangeError",errorStacklength:738}`。原始 `source/wasm.js` 未改，只在 Node 执行前替换内存字符串。

新增分析辅助：

- `scripts/capture_browser_cookies.py --trace-wasm`：在真实 Chrome 中运行站点 fp/wasm，同时记录 `Reflect.set` 写入的 wasm 环境项。
- `scripts/capture_browser_cookies.py` 默认输出增加 `envProfile`，用于记录真实 Chrome 的 `navigator/screen/plugins/WebGL/canvas/iframe` 画像。
- `scripts/generate_cookies.js --trace-env`：Node 侧输出 `wasmTrace` 和 `matchMediaQueries`，用于与浏览器 trace 对比。

关键验证结果：

```text
node_wasm_trace_latest.json vs browser_wasm_trace_latest.json:
  last Reflect.set trace diff_count = 0

Node helper output:
  pr_fp=e94c74962721a68ab05418066e68bf1fa90892f13c2cbc628cd0ef31825c045c
  wasm=d26b7c65fcc34ab72bdb5a05dce32b45

Browser trace output:
  pr_fp=a395c3361242fe6fce7a9962dfc6eedd572312ac2d77d6238c7f89448ac6cb6b
  wasm=0b10300a0ff2cad10a49909851b27352
```

虽然 `Reflect.set` 暴露出来的最终环境项已经完全对齐，Node 仍稳定生成 `wasm=d26b7c65fcc34ab72bdb5a05dce32b45`。用该 Node cookie 实际请求：

```text
python targets\ru_sf_wasm\output\kad_request.py --probe-card \
  --pr-fp e94c74962721a68ab05418066e68bf1fa90892f13c2cbc628cd0ef31825c045c \
  --wasm d26b7c65fcc34ab72bdb5a05dce32b45

captchaGate.json.Result = true
cardProbe.status_code   = 451
cardProbe.classification= blocked_451
```

`output/test01.py` 已调整为“Node 优先，浏览器最后兜底”：

```text
python targets\ru_sf_wasm\output\test01.py

attempt[0]:
  source=node
  status_code=451
  classification=blocked_451
  wasm=d26b7c65fcc34ab72bdb5a05dce32b45

attempt[1]:
  source=browser_fallback
  status_code=200
  classification=case_card_html
  wasm=0b10300a0ff2cad10a49909851b27352
  pr_fp=a395c3361242fe6fce7a9962dfc6eedd572312ac2d77d6238c7f89448ac6cb6b
```

结论：继续修改 Node 环境信息可以把“可见的 wasm 环境特征”对齐到真实 Chrome，但目前仍不能生成服务端认可的 `wasm` cookie。剩余差异大概率不在 `Reflect.set` 暴露的对象字段里，而在 wasm 内部不可见的宿主/realm/原型/Promise/WebAssembly/错误栈/对象身份等行为差异中。当前可交付策略应保持：

1. 默认研究方向：继续定位 wasm 内部最终 hash/分类入口，或更细粒度 hook wasm import/export、内存输入。
2. 运行兜底方向：真实 Chrome/CDP 生成 `pr_fp/wasm`，Python requests 复用 cookie。
3. `test01.py` 当前行为：先尝试 Node；Node 失败后才触发 `browser_fallback`。

## 风险与维护点

- `fp.js`、`fp_bg.wasm`、`wasm.js`、`wasm_bg.wasm` 版本变化后，需要重新下载素材并复测 helper。
- `pr_fp` 取决于本地环境桩，当前值可通过 gate，但如果服务端加强一致性校验，需要调整 UA、WebGL、canvas、navigator 等字段。
- `wasm` cookie 当前稳定生成 `d26b7c65fcc34ab72bdb5a05dce32b45`，有效期约 450 秒。
- 451 与验证码判定属于 cookie gate 之后的独立问题，不应误判为 `pr_fp/wasm` 生成失败。
- DDoS-Guard challenge HTML 属于 cookie gate 之前的外层拦截；优先检查 `__ddg*`、UA、TLS 指纹、请求频率和 IP 状态。
