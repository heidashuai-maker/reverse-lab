# Verification And Replay

Use this reference after `env-diagnose.js` can load the target script. Loading success is only a syntax/runtime milestone; it does not prove the target sign, token, cookie, or encrypted field is accepted by the server.

如果本地脚本已经能生成值，但请求仍失败，先不要直接改 HTTP 客户端。先做三组对照：

1. 浏览器生成的值 + Node/Python 请求是否成功。
2. 本地沙箱生成的值 + 同一 Node/Python 请求是否成功。
3. 浏览器请求与 Node/Python 请求在 TLS、HTTP/2、header、cookie、body 编码上是否一致。

判定规则：

| 对照结果 | 结论 | 下一步 |
| --- | --- | --- |
| 浏览器值可用，本地值不可用 | 环境指纹或本地执行分歧优先 | 进入 `sandbox-fingerprint-validation.md` |
| 浏览器值和本地值都不可用 | 请求契约或协议层问题优先 | 检查 TLS/HTTP2/header/cookie/IP/账号绑定 |
| 两者都可用但不稳定 | 时效、随机数、session 或并发问题 | 固定 fixture，检查时间/nonce/cookie 刷新 |
| HTTP 200 但空 body / 少字段 | 风控态，不是成功态 | 对比浏览器正常响应体特征 |

## Function Verification

`success: true` is not functional success. Verify the target behavior in a project-local runner such as `js_reverse_cache/env/run.js`, using the same environment modules selected during diagnosis.

Recommended flow:

1. Build `js_reverse_cache/env/run.js` with the same env modules and the target script.
2. Trigger the target behavior, such as an SDK init call, an XHR send, or a direct sign function call.
3. Check output shape against browser evidence, such as `a_bogus` length, prefix, segment count, encoding, or cookie name.
4. Only then package the callable sign/token interface or try HTTP replay.

For hook-style SDKs, keep this loading order:

```text
env modules -> fake XMLHttpRequest -> target JS -> capture hook -> init(config) -> trigger request
```

Important details:

1. Fake `XMLHttpRequest` must exist before loading the target JS if the target patches its prototype at load time.
2. Capture hooks such as `URLSearchParams.append` should be injected after the target JS if the target may replace native APIs with polyfills.
3. SDK `init` or `setup` parameters must be captured from the browser when they decide path matching or feature switches.

Common failures after load succeeds:

| Symptom | Likely Cause | Check |
|---|---|---|
| Sign is `undefined` | Missing crypto/performance dependency | Review selected env modules |
| Hook runs but does not sign | Missing SDK init params or path whitelist | Capture init params in the browser |
| Capture hook never fires | Hook injected before a target polyfill overwrote it | Move capture hook after target JS |
| JSVMP silently fails | Internal try/catch swallowed errors | Instrument known error exits cautiously |
| Sign length differs from browser | Environment fingerprint mismatch | Collect real browser seeds and patch minimally |

## Packaging A Callable Interface

After function verification passes, extract the runner into a small callable module, commonly `js_reverse_cache/env/sign.js`:

```javascript
function sign(url) {
  window.__captured_a_bogus = null;
  const xhr = new XMLHttpRequest();
  xhr.open('GET', url, true);
  xhr.setRequestHeader('Accept', 'application/json, text/plain, */*');
  xhr.send(null);
  return window.__captured_a_bogus;
}

module.exports = sign;

if (require.main === module) {
  const url = process.argv[2] || process.env.SIGN_URL;
  if (!url) {
    console.error('Usage: node sign.js <url>');
    process.exit(1);
  }
  process.stdout.write(sign(url) || '');
}
```

Prefer an HTTP middleware for Python replay when process environment differences affect subprocess execution:

```javascript
const http = require('http');
const sign = require('./sign');
const PORT = 3456;

const server = http.createServer((req, res) => {
  if (req.method !== 'POST' || req.url !== '/sign') {
    res.writeHead(404);
    res.end('Not Found');
    return;
  }

  let body = '';
  req.on('data', (chunk) => body += chunk);
  req.on('end', () => {
    try {
      const { url } = JSON.parse(body);
      const result = sign(url);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ result: result || '', length: (result || '').length }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
  });
});

server.listen(PORT, () => console.log(`sign server on http://localhost:${PORT}/sign`));
```

## HTTP Replay Checks

Validate in this order:

1. Format check: run `node js_reverse_cache/env/run.js` and compare sign shape with browser evidence.
2. Middleware check: call `POST http://localhost:3456/sign` with a known URL.
3. Request replay: send the real API request with the returned sign and the same browser-side request contract.
4. Stability check: repeat the same validated flow at least 3 times; for time-sensitive JSVMP / WAF cookie / environment fingerprint signatures, repeat at least 5 times and record failures.

Python request rules:

1. Use `requests.get(base_url, params=params, cookies=cookies)` or the equivalent `curl_cffi.requests` call.
2. Keep `cookies` as a dict or cookie jar; do not stuff a raw cookie string into `headers["cookie"]` unless the target explicitly requires manual header replay.
3. Do not manually pre-quote the generated sign unless browser evidence proves the exact encoded form.
4. Rebuild time-sensitive sign/header/token values inside pagination or retry loops.

Minimal replay skeleton:

```python
from curl_cffi import requests

SIGN_SERVER = "http://localhost:3456/sign"


def get_sign(url):
    resp = requests.post(SIGN_SERVER, json={"url": url}, impersonate="chrome136")
    return resp.json().get("result") or None


headers = {"user-agent": "...", "referer": "..."}
cookies = {"ttwid": "...", "odin_tt": "..."}
params = {"aid": "6383", "sec_user_id": "...", "msToken": "..."}

base_url = "https://target.example/api/path/"
prepared = requests.Request("GET", base_url, params=params).prepare()
params["a_bogus"] = get_sign(prepared.url)

response = requests.get(base_url, headers=headers, cookies=cookies, params=params, impersonate="chrome136")
print(response.status_code, response.text)
```
