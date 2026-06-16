import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import websocket


BASE_URL = "https://kad.arbitr.ru"
DEFAULT_CARD_ID = "566bf0a7-8ccc-4aef-9b45-a46be35197bf"
DEFAULT_PROXY = "socks5h://10.86.10.212:8204"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TARGET_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = Path(__file__).resolve().parents[3] / "js_reverse_cache" / "ru_sf_wasm"


def find_chrome():
    candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("msedge"),
        shutil.which("msedge.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("Chrome or Edge executable was not found")


class CdpClient:
    def __init__(self, websocket_url):
        self.ws = websocket.create_connection(websocket_url, timeout=20)
        self.next_id = 1

    def close(self):
        self.ws.close()

    def call(self, method, params=None, timeout=20):
        message_id = self.next_id
        self.next_id += 1
        self.ws.send(json.dumps({
            "id": message_id,
            "method": method,
            "params": params or {},
        }))
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self.ws.recv()
            message = json.loads(raw)
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise RuntimeError(f"{method} failed: {message['error']}")
            if "exceptionDetails" in message.get("result", {}):
                raise RuntimeError(f"{method} exception: {message['result']['exceptionDetails']}")
            return message.get("result", {})
        raise TimeoutError(f"CDP call timed out: {method}")


def wait_for_json(url, timeout=20):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return response.json()
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"CDP endpoint did not become ready: {url}: {last_error}")


def launch_chrome(chrome_path, user_data_dir, port, proxy=None, headless=False):
    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-popup-blocking",
        "--disable-blink-features=AutomationControlled",
        "--lang=ru-RU",
        "about:blank",
    ]
    if proxy:
        if proxy.startswith("socks5h://"):
            args.insert(-1, "--proxy-server=socks5://" + proxy[len("socks5h://"):])
        else:
            args.insert(-1, f"--proxy-server={proxy}")
    if headless:
        args.insert(-1, "--headless=new")
        args.insert(-1, "--window-size=1365,900")

    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def parse_cookie_header(cookie_header):
    result = {}
    for item in cookie_header.split(";"):
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        result[name.strip()] = value.strip()
    return result


def classify_card_response(response):
    text = response.text or ""
    if response.status_code == 451 or "/static/img/blocked.png" in text or "Доступ заблокирован" in text:
        return "blocked_451"
    if "b-case-header" in text or "js-case-header-case_num" in text:
        return "case_card_html"
    if "b-pravocaptcha-title" in text or ("pravocaptcha" in text and "RecaptchaToken" in text):
        return "pravocaptcha_gate"
    if "DDoS-Guard" in text or "/.well-known/ddos-guard/js-challenge/" in text:
        return "ddos_guard_challenge"
    return "unknown"


def generate_cookies_in_page(client, trace_wasm=False):
    expression = r"""
(async () => {
  const traceEnabled = __TRACE_WASM__;
  const wasmTrace = [];
  const traceValue = (value) => {
    if (value === null) return 'null';
    if (typeof value === 'undefined') return 'undefined';
    if (typeof value === 'string') return JSON.stringify(value.length > 120 ? value.slice(0, 117) + '...' : value);
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) return JSON.stringify(value);
    if (ArrayBuffer.isView(value)) return `${value.constructor.name}[${Array.from(value).join(',')}]`;
    try { return `${Object.prototype.toString.call(value)} ${JSON.stringify(value)}`; } catch (error) { return Object.prototype.toString.call(value); }
  };
  const installTrace = () => {
    if (!traceEnabled) return;
    const originalReflectSet = Reflect.set;
    Reflect.set = function(target, key, value, receiver) {
      if (typeof key === 'string') wasmTrace.push([key, traceValue(value)]);
      if (arguments.length >= 4) return originalReflectSet(target, key, value, receiver);
      return originalReflectSet(target, key, value);
    };
  };
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const loadScript = (src) => new Promise((resolve, reject) => {
    const s = document.createElement('script');
    const timer = setTimeout(() => reject(new Error('script load timed out: ' + src)), 30000);
    s.src = src;
    s.onload = () => { clearTimeout(timer); resolve(); };
    s.onerror = () => { clearTimeout(timer); reject(new Error('script load failed: ' + src)); };
    document.head.appendChild(s);
  });

  if (document.title === 'DDoS-Guard' || document.documentElement.innerHTML.includes('/.well-known/ddos-guard/js-challenge/')) {
    throw new Error('still on DDoS-Guard challenge: ' + location.href);
  }

  if (!window.fp) {
    await loadScript('/Content/Static/js/common/fp.js?_=1705670688006');
  }
  await window.fp.default('/Content/Static/js/common/fp_bg.wasm?_=1705670688006');
  await window.fp.get();

  installTrace();
  if (!window.wasm) {
    await loadScript('/Wasm/api/v1/wasm.js?_=' + Date.now());
  }
  await window.wasm.default('/Wasm/api/v1/wasm_bg.wasm?_=' + Date.now());
  window.wasm.main();

  await sleep(800);
  return {
    href: location.href,
    title: document.title,
    cookie: document.cookie,
    userAgent: navigator.userAgent,
    webdriver: navigator.webdriver,
    pr_fp: (document.cookie.match(/(?:^|;\s*)pr_fp=([^;]+)/) || [])[1] || null,
    wasm: (document.cookie.match(/(?:^|;\s*)wasm=([^;]+)/) || [])[1] || null,
    wasmTrace: traceEnabled ? wasmTrace : null
  };
})()
"""
    expression = expression.replace("__TRACE_WASM__", "true" if trace_wasm else "false")
    result = client.call(
        "Runtime.evaluate",
        {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
        },
        timeout=90,
    )
    value = result.get("result", {}).get("value")
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected Runtime.evaluate result: {result}")
    if not value.get("pr_fp") or not value.get("wasm"):
        raise RuntimeError(f"browser did not produce pr_fp/wasm: {value}")
    value["cookies"] = parse_cookie_header(value["cookie"])
    return value


def collect_environment_profile(client):
    expression = r"""
(async () => {
  const simpleValue = (value) => {
    if (value === null) return null;
    const type = typeof value;
    if (type === 'string' || type === 'number' || type === 'boolean' || type === 'undefined') {
      return value;
    }
    if (Array.isArray(value)) return value.slice(0, 20);
    if (value && typeof value.length === 'number' && value.item) {
      const items = [];
      for (let i = 0; i < Math.min(value.length, 20); i += 1) {
        const item = value.item(i) || value[i];
        items.push(item ? {
          name: item.name,
          filename: item.filename,
          description: item.description,
          type: item.type,
          suffixes: item.suffixes,
          length: item.length
        } : null);
      }
      return { length: value.length, items };
    }
    return `[${Object.prototype.toString.call(value)}]`;
  };
  const fnText = (fn) => {
    try { return Function.prototype.toString.call(fn).slice(0, 120); } catch (error) { return String(error); }
  };
  const descriptorOf = (object, key) => {
    let cursor = object;
    let level = 0;
    while (cursor) {
      const descriptor = Object.getOwnPropertyDescriptor(cursor, key);
      if (descriptor) {
        const result = {
          level,
          enumerable: descriptor.enumerable,
          configurable: descriptor.configurable,
          hasGetter: typeof descriptor.get === 'function',
          hasSetter: typeof descriptor.set === 'function',
          writable: Object.prototype.hasOwnProperty.call(descriptor, 'writable') ? descriptor.writable : null,
          valueType: Object.prototype.hasOwnProperty.call(descriptor, 'value') ? typeof descriptor.value : null,
        };
        if (descriptor.get) result.getter = fnText(descriptor.get);
        if (descriptor.set) result.setter = fnText(descriptor.set);
        if (Object.prototype.hasOwnProperty.call(descriptor, 'value')) result.value = simpleValue(descriptor.value);
        return result;
      }
      cursor = Object.getPrototypeOf(cursor);
      level += 1;
    }
    return null;
  };
  const objectKeys = (object) => {
    try { return Object.getOwnPropertyNames(object).slice(0, 80); } catch (error) { return [String(error)]; }
  };
  const descriptors = (object, keys) => Object.fromEntries(keys.map((key) => [key, descriptorOf(object, key)]));
  const hashString = async (input) => {
    const data = new TextEncoder().encode(input);
    const digest = await crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, '0')).join('');
  };

  const invalidWebSocket = (() => {
    try {
      new WebSocket('itsgonnafail');
      return { ok: true };
    } catch (error) {
      return {
        name: error.name,
        message: error.message,
        constructorName: error.constructor && error.constructor.name,
        toString: String(error)
      };
    }
  })();

  const permissionsNotification = navigator.permissions && navigator.permissions.query
    ? await navigator.permissions.query({ name: 'notifications' }).then((item) => ({
      state: item.state,
      onchange: item.onchange,
      constructorName: item.constructor && item.constructor.name
    })).catch((error) => ({ error: String(error) }))
    : null;

  const canvas = document.createElement('canvas');
  canvas.width = 200;
  canvas.height = 50;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.textBaseline = 'top';
    ctx.font = '16px Arial';
    ctx.fillStyle = '#f60';
    ctx.fillRect(0, 0, 80, 30);
    ctx.fillStyle = '#069';
    ctx.fillText('BrowserLeaks,com <canvas> 1.0', 2, 2);
  }
  const canvasDataUrl = canvas.toDataURL();
  const imageData = ctx ? Array.from(ctx.getImageData(0, 0, 1, 1).data) : null;

  const glCanvas = document.createElement('canvas');
  const gl = glCanvas.getContext('webgl') || glCanvas.getContext('experimental-webgl');
  let webgl = null;
  if (gl) {
    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
    webgl = {
      vendor: gl.getParameter(gl.VENDOR),
      renderer: gl.getParameter(gl.RENDERER),
      version: gl.getParameter(gl.VERSION),
      shadingLanguageVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
      unmaskedVendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : null,
      unmaskedRenderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : null,
      extensions: gl.getSupportedExtensions(),
    };
  }

  const iframe = document.createElement('iframe');
  document.body.appendChild(iframe);
  const iframeWindow = iframe.contentWindow;
  const iframeProfile = iframeWindow ? {
    hasChrome: !!iframeWindow.chrome,
    webdriver: iframeWindow.navigator && iframeWindow.navigator.webdriver,
    navigatorPrototypeKeys: iframeWindow.navigator ? objectKeys(Object.getPrototypeOf(iframeWindow.navigator)) : [],
    userAgent: iframeWindow.navigator && iframeWindow.navigator.userAgent,
  } : null;
  iframe.remove();

  const video = document.createElement('video');
  const audio = document.createElement('audio');
  return {
    navigator: {
      ownKeys: objectKeys(navigator),
      prototypeKeys: objectKeys(Object.getPrototypeOf(navigator)),
      descriptors: descriptors(navigator, [
        'userAgent', 'appVersion', 'platform', 'vendor', 'language', 'languages',
        'webdriver', 'hardwareConcurrency', 'deviceMemory', 'maxTouchPoints',
        'doNotTrack', 'productSub', 'plugins', 'mimeTypes', 'permissions'
      ]),
      values: {
        userAgent: navigator.userAgent,
        appVersion: navigator.appVersion,
        platform: navigator.platform,
        vendor: navigator.vendor,
        language: navigator.language,
        languages: navigator.languages,
        webdriver: navigator.webdriver,
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: navigator.deviceMemory,
        maxTouchPoints: navigator.maxTouchPoints,
        doNotTrack: navigator.doNotTrack,
        productSub: navigator.productSub,
        plugins: simpleValue(navigator.plugins),
        mimeTypes: simpleValue(navigator.mimeTypes),
      },
    },
    screen: {
      ownKeys: objectKeys(screen),
      prototypeKeys: objectKeys(Object.getPrototypeOf(screen)),
      descriptors: descriptors(screen, ['width', 'height', 'availWidth', 'availHeight', 'colorDepth', 'pixelDepth']),
      values: {
        width: screen.width,
        height: screen.height,
        availWidth: screen.availWidth,
        availHeight: screen.availHeight,
        colorDepth: screen.colorDepth,
        pixelDepth: screen.pixelDepth,
      },
    },
    window: {
      innerWidth,
      innerHeight,
      outerWidth,
      outerHeight,
      devicePixelRatio,
      openDatabaseType: typeof openDatabase,
      indexedDBType: typeof indexedDB,
      localStorageType: typeof localStorage,
      sessionStorageType: typeof sessionStorage,
      chromeKeys: window.chrome ? objectKeys(window.chrome) : null,
      chromeRuntimeKeys: window.chrome && window.chrome.runtime ? objectKeys(window.chrome.runtime) : null,
    },
    functions: {
      evalToString: fnText(eval),
      setTimeoutToString: fnText(setTimeout),
      navigatorPermissionsQueryToString: navigator.permissions && navigator.permissions.query ? fnText(navigator.permissions.query) : null,
      canvasToDataURLToString: fnText(HTMLCanvasElement.prototype.toDataURL),
      websocketToString: fnText(WebSocket),
    },
    permissionsNotification,
    invalidWebSocket,
    iframe: iframeProfile,
    canvas: {
      dataUrlLength: canvasDataUrl.length,
      dataUrlPrefix: canvasDataUrl.slice(0, 80),
      dataUrlSha256: await hashString(canvasDataUrl),
      imageData00: imageData,
    },
    webgl,
    media: {
      videoMp4: video.canPlayType('video/mp4; codecs="avc1.42E01E"'),
      videoWebm: video.canPlayType('video/webm; codecs="vp8, vorbis"'),
      audioMp3: audio.canPlayType('audio/mpeg'),
      audioOgg: audio.canPlayType('audio/ogg; codecs="vorbis"'),
    },
    time: {
      timezoneOffset: new Date().getTimezoneOffset(),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    },
  };
})()
"""
    result = client.call(
        "Runtime.evaluate",
        {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
        },
        timeout=90,
    )
    value = result.get("result", {}).get("value")
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected environment profile result: {result}")
    return value


def validate_with_requests(cookies, proxy, card_id):
    session = requests.Session()
    session.cookies.update({
        "pr_fp": cookies["pr_fp"],
        "wasm": cookies["wasm"],
    })
    proxies = None
    if proxy:
        proxies = {"http": proxy, "https": proxy}
    url = f"{BASE_URL}/Card/{card_id}" if not card_id.startswith("http") else card_id
    response = session.get(
        url,
        headers={
            "user-agent": DEFAULT_UA,
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
                "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "referer": url,
        },
        proxies=proxies,
        timeout=45,
    )
    return {
        "status_code": response.status_code,
        "classification": classify_card_response(response),
        "text_preview": response.text[:500],
    }


def build_parser():
    parser = argparse.ArgumentParser(description="Capture usable pr_fp/wasm cookies from real Chrome.")
    parser.add_argument("--chrome", help="Chrome or Edge executable path.")
    parser.add_argument("--port", type=int, default=9223)
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    parser.add_argument("--card-id", default=DEFAULT_CARD_ID)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--keep-profile", action="store_true")
    parser.add_argument("--trace-wasm", action="store_true")
    parser.add_argument("--output", default=str(TARGET_DIR / "samples" / "browser_generated_cookies_latest.json"))
    return parser


def main():
    args = build_parser().parse_args()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    chrome_path = args.chrome or find_chrome()
    profile_dir = Path(tempfile.mkdtemp(prefix="chrome_profile_", dir=str(CACHE_DIR)))
    process = launch_chrome(chrome_path, profile_dir, args.port, proxy=args.proxy, headless=args.headless)
    try:
        version = wait_for_json(f"http://127.0.0.1:{args.port}/json/version")
        tabs = wait_for_json(f"http://127.0.0.1:{args.port}/json/list")
        page = next((item for item in tabs if item.get("type") == "page"), tabs[0])
        client = CdpClient(page["webSocketDebuggerUrl"])
        try:
            client.call("Page.enable")
            client.call("Network.enable")
            client.call("Network.setUserAgentOverride", {"userAgent": DEFAULT_UA})
            client.call("Page.navigate", {"url": BASE_URL + "/"})
            time.sleep(8)
            cookie_info = generate_cookies_in_page(client, trace_wasm=args.trace_wasm)
            env_profile = collect_environment_profile(client)
        finally:
            client.close()

        validation = validate_with_requests(cookie_info, args.proxy, args.card_id)
        output = {
            "chrome": chrome_path,
            "debugger": version.get("Browser"),
            "headless": args.headless,
            "profileDir": str(profile_dir),
            "cookies": {
                "pr_fp": cookie_info["pr_fp"],
                "wasm": cookie_info["wasm"],
            },
            "browserContext": {
                "href": cookie_info.get("href"),
                "title": cookie_info.get("title"),
                "userAgent": cookie_info.get("userAgent"),
                "webdriver": cookie_info.get("webdriver"),
            },
            "envProfile": env_profile,
            "wasmTrace": cookie_info.get("wasmTrace"),
            "requestValidation": validation,
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        if not args.keep_profile:
            shutil.rmtree(profile_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
