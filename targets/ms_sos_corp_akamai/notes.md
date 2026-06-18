# Mississippi SOS Corp Akamai 初步分析

## 结论

当前网站的公司详情链路**确认使用 Akamai 技术**，置信度高。证据不是只来自首页 CDN 头，而是覆盖了搜索入口、搜索 API、Akamai sensor、sensor POST、详情 XHR、详情 HTML 内联 Akamai RUM 变量，以及裸请求 403 阻断样本。

本次只做 observe / capture 阶段，不做 Akamai 绕过、sensor 还原或纯协议移植。

## 目标与样本

- 入口 URL：`https://corp.sos.ms.gov/corp/portal/c/page/corpbusinessidsearch/portal.aspx`
- 搜索样本：`WALMART`
- 详情样本：`WAL-MART ASSOCIATES, INC.`
- Business ID：`636136`
- FilingId：`31734e49-817e-4e9f-9ea0-4ec10aa212a9`
- 详情 URL：`/corp/portal/c/page/corpbusinessidsearch/ViewXSLTFileByName.aspx?providerName=MSBSD_CorporationBusinessDetails&FilingId=31734e49-817e-4e9f-9ea0-4ec10aa212a9`

## Akamai 证据

1. 匿名 HTTP 探测：
   - `HEAD /corp/portal/c/page/corpbusinessidsearch/portal.aspx` 返回 `200`，响应头包含 `Akamai-GRN`、`Server-Timing: ak_p`、`Alt-Svc: h3`。
   - 普通 `GET` 入口页返回 `403 Access Denied`，响应体引用 `errors.edgesuite.net`，响应头仍包含 `Akamai-GRN` 和 `ak_p`。
   - 产物：`samples/http_probe_search_head.txt`、`samples/http_probe_search_get.headers.txt`、`source/search_page_anonymous_get.html`。

2. Camoufox 浏览器入口页：
   - 文档请求 `200`。
   - 响应头包含 `x-akamai-transformed: 9 46869 0 pmb=mRUM, 1`、`Akamai-GRN`、`Server-Timing: cdn-cache; edge; origin; ak_p`。
   - 响应 `Set-Cookie` 出现 `bm_ss`、`bm_s`、`bm_so`，浏览器最终 cookie jar 还有 `bm_lso`。
   - 产物：`samples/browser-state-camoufox.json`、`samples/browser-env-camoufox.json`。

3. Akamai sensor：
   - 页面加载同源随机路径脚本：`/ywwgo-/sPxAD/ZoXv-/tA/mhEGcVuVQ5/FTFFIgE/ex8AeTJh/P3tQ?v=e35a49ea-ee41-802d-91e0-9c48e36b0210`。
   - 脚本体约 `418501` 字节，响应头有 `stored-attribute-sha-checksum`、`Akamai-GRN`、`ak_p`。
   - 搜索后向同一路径发 `POST`，body 是编码后的浏览器 sensor payload，响应再次 `Set-Cookie: bm_s`。
   - 产物：`source/akamai_sensor_ywwgo.js`、`samples/network.jsonl`。

4. 详情 XHR 直接证据：
   - 点击第一条 `Details` 后，浏览器请求：
     `ViewXSLTFileByName.aspx?providerName=MSBSD_CorporationBusinessDetails&FilingId=31734e49-817e-4e9f-9ea0-4ec10aa212a9`
   - 该详情 XHR 返回 `200`，响应头包含：
     - `x-akamai-transformed: 9 7354 0 pmb=mRUM, 1`
     - `Akamai-GRN: 0.27f41002.1781712004.83e72426`
     - `Server-Timing: cdn-cache; desc=MISS, edge; dur=138, origin; dur=169, ak_p; ...`
   - 详情 HTML 内还有 `BOOMR.plugins.AK`，变量包含 `ak.v`、`ak.cp`、`ak.ai`、`ak.rid`、`ak.gh`、`ak.tlsv` 等 Akamai RUM 字段。

5. 浏览器与裸请求分歧：
   - 同一详情 URL 在 Camoufox 浏览器中返回 `200`。
   - 使用 `scripts/probe_akamai_headers.ps1` 读取 Camoufox 导出的 cookie 后再用 `curl` 请求详情，仍返回 `403 Access Denied`，响应体引用 `errors.edgesuite.net`。
   - 这说明详情访问不是普通 cookie replay，至少还受 Akamai 边缘判定、浏览器行为、TLS/HTTP 指纹或 sensor 状态约束。

## 业务详情链路

已保存业务脚本：`source/BusinessSearchScriptV2.js`。

链路如下：

```text
search page
  -> #businessNameSearchButton
  -> BusinessNameSearch()
  -> POST /corp/Services/MS/CorpServices.asmx/BusinessNameSearch
  -> result row contains FilingId
  -> Details command
  -> ShowBusinessDetails()
  -> showModalBusinessDetails(filingId, title)
  -> GET ViewXSLTFileByName.aspx?providerName=MSBSD_CorporationBusinessDetails&FilingId=<FilingId>
  -> detail HTML modal
```

关键位置：

- `BusinessSearchScriptV2.js:291`：`BusinessNameSearch()` 构造搜索 JSON 并调用 `/BusinessNameSearch`。
- `BusinessSearchScriptV2.js:386` / `:387`：业务名结果 grid 的 `Details` 按钮绑定 `ShowBusinessDetails`。
- `BusinessSearchScriptV2.js:433`：`ShowBusinessDetails()` 从当前行读取 `dataItem["FilingId"]`。
- `BusinessSearchScriptV2.js:232` / `:239`：`showModalBusinessDetails()` 拼接详情 URL。

## 产物索引

- `samples/task.json`：任务摘要与样本。
- `samples/network.jsonl`：关键请求、响应头和结论。
- `samples/scripts.jsonl`：关键脚本与业务链路。
- `samples/runtime-evidence.jsonl`：浏览器操作、cookie 和 browser-vs-curl 分歧记录。
- `samples/tool-check-camoufox.json`：Camoufox MCP 自检。
- `samples/browser-env-camoufox.json`：Camoufox/Firefox 家族环境基准。
- `samples/browser-state-camoufox.json`：Camoufox 导出的 cookie/storage 状态，含真实 cookie 值。
- `source/BusinessSearchScriptV2.js`：业务搜索与详情入口脚本。
- `source/akamai_sensor_ywwgo.js`：同源随机路径 Akamai sensor 脚本。
- `source/search_page_anonymous_get.html`：匿名 GET 入口页被 Akamai 403 的样本。
- `source/detail_636136_browser_cookie.html`：带导出 cookie 的 `curl` 详情请求仍被 Akamai 403 的样本。
- `source/CorporationBusinessDetails_anonymous_403.html`：裸请求详情 JS 被 Akamai 403 的样本。
- `scripts/probe_akamai_headers.ps1`：可复跑的 HTTP 头与阻断样本采集脚本。
- `output/akamai_assessment.json`：结构化侦察结论。

## 后续建议

如果只是证明是否用了 Akamai，当前证据已经闭环。如果后续要做采集落地，不建议直接写普通 requests spider；至少先做两条路线评估：

1. 自动化骨架：用 Camoufox/浏览器维持 sensor 与 cookie 状态，验证批量搜索和详情点击的稳定性。
2. 专项还原：单独分析 Akamai sensor、`bm_s` 更新、TLS/HTTP 指纹和详情请求放行条件，再判断是否能做纯协议。

当前不建议把 `browser-state-camoufox.json` 中的 cookie 当作长期可复用凭证，因为本次复放已经证明 cookie 复用不足以通过详情请求。
