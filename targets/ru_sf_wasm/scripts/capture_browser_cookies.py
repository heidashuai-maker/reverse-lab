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


def generate_cookies_in_page(client, trace_wasm=False, trace_wasm_imports=False, trace_wasm_heap=False):
    expression = r"""
(async () => {
  const traceEnabled = __TRACE_WASM__;
  const importTraceEnabled = __TRACE_WASM_IMPORTS__;
  const heapTraceEnabled = __TRACE_WASM_HEAP__;
  const wasmTrace = [];
  const wasmImportTrace = [];
  const wasmHeapTrace = [];
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
  const installWasmImportTrace = () => {
    if (!importTraceEnabled) return;
    const originalInstantiate = WebAssembly.instantiate;
    const originalInstantiateStreaming = WebAssembly.instantiateStreaming;
    const decoder = new TextDecoder('utf-8', {ignoreBOM: true, fatal: false});
    let sequence = 0;
    let currentExports = null;

    const captureExports = (result) => {
      const instance = result instanceof WebAssembly.Instance ? result : result && result.instance;
      if (instance && instance.exports) {
        currentExports = instance.exports;
        wasmImportTrace.push({
          phase: 'exports',
          exports: Object.keys(currentExports).sort(),
          hasMemory: currentExports.memory instanceof WebAssembly.Memory,
        });
      }
      return result;
    };

    const readWasmString = (pointer, length) => {
      if (!currentExports || !(currentExports.memory instanceof WebAssembly.Memory)) return null;
      if (!Number.isInteger(pointer) || !Number.isInteger(length) || pointer < 0 || length < 0) return null;
      try {
        const bytes = new Uint8Array(currentExports.memory.buffer, pointer, length);
        return decoder.decode(bytes);
      } catch (error) {
        return `[decode-error:${error && error.message ? error.message : error}]`;
      }
    };

    const readWasmI32 = (pointer) => {
      if (!currentExports || !(currentExports.memory instanceof WebAssembly.Memory)) return null;
      try {
        return new DataView(currentExports.memory.buffer).getInt32(pointer, true);
      } catch (error) {
        return null;
      }
    };

    const readWasmF64 = (pointer) => {
      if (!currentExports || !(currentExports.memory instanceof WebAssembly.Memory)) return null;
      try {
        return new DataView(currentExports.memory.buffer).getFloat64(pointer, true);
      } catch (error) {
        return null;
      }
    };

    const readWasmOutString = (outPointer) => {
      const pointer = readWasmI32(outPointer);
      const length = readWasmI32(outPointer + 4);
      if (pointer === null || length === null) return null;
      return {pointer, length, value: readWasmString(pointer, length)};
    };

    const describeImportValue = (value) => {
      if (value === null) return {type: 'null', value: null};
      if (typeof value === 'undefined') return {type: 'undefined'};
      if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'string') {
        return {type: typeof value, value};
      }
      if (ArrayBuffer.isView(value)) {
        return {
          type: value.constructor.name,
          length: value.length,
          preview: Array.from(value.slice ? value.slice(0, 16) : value).slice(0, 16),
        };
      }
      if (value instanceof WebAssembly.Instance) return {type: 'WebAssembly.Instance'};
      if (value instanceof WebAssembly.Module) return {type: 'WebAssembly.Module'};
      if (value instanceof WebAssembly.Memory) return {type: 'WebAssembly.Memory'};
      if (value && typeof value.then === 'function') return {type: 'Promise'};
      try {
        return {
          type: Object.prototype.toString.call(value),
          constructorName: value && value.constructor && value.constructor.name,
        };
      } catch (error) {
        return {type: typeof value};
      }
    };

    const describeImportError = (error) => ({
      name: error && error.name,
      message: error && error.message,
      stackHead: error && error.stack ? String(error.stack).split('\n').slice(0, 3) : undefined,
    });

    const stringPairsByName = {
      __wbindgen_string_new: [[0, 1, 'string']],
      __wbg_testregexp_5e5e24c14542431c: [[0, 1, 'pattern']],
      __wbg_getfirstmatch_9679c7c35bbd6ccf: [[1, 2, 'input'], [3, 4, 'pattern']],
      __wbg_newnoargs_c4b2cbbd30e2d057: [[0, 1, 'body']],
      __wbg_join_b6efd1e111c0dd52: [[1, 2, 'separator']],
      __wbg_setcookie_b04b7af29c82f976: [[0, 1, 'cookie']],
      __widl_f_create_element_Document: [[1, 2, 'tagName']],
      __widl_f_create_event_Document: [[1, 2, 'eventName']],
      __widl_f_get_element_by_id_Document: [[1, 2, 'id']],
      __widl_f_has_attribute_Element: [[1, 2, 'attribute']],
      __widl_f_set_attribute_Element: [[1, 2, 'attribute'], [3, 4, 'value']],
      __widl_f_get_context_HTMLCanvasElement: [[1, 2, 'contextId']],
      __widl_f_set_srcdoc_HTMLIFrameElement: [[1, 2, 'srcdoc']],
      __widl_f_set_value_HTMLInputElement: [[1, 2, 'value']],
      __widl_f_get_extension_WebGLRenderingContext: [[1, 2, 'extension']],
      __widl_f_match_media_Window: [[1, 2, 'query']],
    };

    const describeImportArgs = (name, args) => {
      const values = Array.from(args, describeImportValue);
      const decodedStrings = [];
      for (const [pointerIndex, lengthIndex, label] of stringPairsByName[name] || []) {
        decodedStrings.push({
          label,
          pointer: args[pointerIndex],
          length: args[lengthIndex],
          value: readWasmString(args[pointerIndex], args[lengthIndex]),
        });
      }
      if (decodedStrings.length > 0) values.push({decodedStrings});
      if (name === '__wbg_setcookie_b04b7af29c82f976') {
        values.push({decodedCookie: readWasmString(args[0], args[1])});
      }
      return values;
    };

    const outStringNames = new Set([
      '__wbg_functiontostring_a49d6e11424fca6f',
      '__wbg_getfirstmatch_9679c7c35bbd6ccf',
      '__wbindgen_debug_string',
      '__wbindgen_string_get',
      '__widl_f_hostname_Location',
      '__widl_f_protocol_Location',
      '__widl_f_user_agent_Navigator',
      '__widl_f_value_HTMLInputElement',
    ]);

    const describePostCallMemory = (name, args) => {
      if (outStringNames.has(name)) return {outString: readWasmOutString(args[0])};
      if (name === '__wbindgen_number_get') return {isNumber: Boolean(readWasmI32(args[0])), value: readWasmF64(args[0] + 8)};
      return null;
    };

    const shouldCaptureImportStack = (name) => (
      name === '__wbg_setcookie_b04b7af29c82f976' ||
      name === '__wbg_getfirstmatch_9679c7c35bbd6ccf' ||
      name === '__widl_f_hostname_Location' ||
      name === '__widl_f_user_agent_Navigator' ||
      name === '__wbg_testregexp_5e5e24c14542431c' ||
      name === '__wbg_stringtonumber_95f60f6c5fcb82cc' ||
      name === '__wbg_getparser_31d8e9a24afafd4c'
    );

    const captureImportStack = () => {
      const stack = new Error('ru-wasm-import-stack').stack;
      return stack ? String(stack).split('\\n').slice(1, 14) : [];
    };

    const wrapImports = (imports) => {
      if (!imports || !imports.wbg) return imports;
      for (const [name, original] of Object.entries(imports.wbg)) {
        if (typeof original !== 'function' || original.__ruWasmImportWrapped) continue;
        const wrapped = function wasmImportWrapper(...args) {
          const seq = ++sequence;
          const entry = {seq, phase: 'call', name, args: describeImportArgs(name, args)};
          if (shouldCaptureImportStack(name)) entry.stack = captureImportStack();
          wasmImportTrace.push(entry);
          try {
            const result = original.apply(this, args);
            entry.result = describeImportValue(result);
            const postCallMemory = describePostCallMemory(name, args);
            if (postCallMemory) entry.memory = postCallMemory;
            if (name === '__wbg_setcookie_b04b7af29c82f976') entry.documentCookieAfter = document.cookie;
            if (result && typeof result.then === 'function') {
              result.then(
                (value) => wasmImportTrace.push({seq, phase: 'promise-resolve', name, value: describeImportValue(value)}),
                (error) => wasmImportTrace.push({seq, phase: 'promise-reject', name, error: describeImportError(error)}),
              );
            }
            return result;
          } catch (error) {
            entry.throw = describeImportError(error);
            throw error;
          }
        };
        Object.defineProperty(wrapped, '__ruWasmImportWrapped', {value: true});
        imports.wbg[name] = wrapped;
      }
      wasmImportTrace.push({
        phase: 'imports-wrapped',
        count: Object.keys(imports.wbg).length,
        names: Object.keys(imports.wbg).sort(),
      });
      return imports;
    };

    WebAssembly.instantiate = function instantiate(source, imports) {
      wrapImports(imports);
      const result = originalInstantiate.call(WebAssembly, source, imports);
      if (result && typeof result.then === 'function') return result.then(captureExports);
      return captureExports(result);
    };

    if (typeof originalInstantiateStreaming === 'function') {
      WebAssembly.instantiateStreaming = function instantiateStreaming(source, imports) {
        wrapImports(imports);
        const result = originalInstantiateStreaming.call(WebAssembly, source, imports);
        if (result && typeof result.then === 'function') return result.then(captureExports);
        return captureExports(result);
      };
    }
  };
  const instrumentWasmRuntimeSource = (source) => {
    const preambleNeedle = '"use strict";';
    const preambleReplacement = `"use strict";function __ruWasmRecord(phase,data){try{var trace=globalThis.__ruWasmHeapTrace;if(!trace)return;var limit=globalThis.__ruWasmHeapTraceLimit||200000;if(trace.length>=limit)return;var entry={phase:phase,seq:globalThis.__ruWasmHeapTraceSeq__=(globalThis.__ruWasmHeapTraceSeq__||0)+1};if(data){for(var key in data)entry[key]=data[key]}trace.push(entry)}catch(_){}}function __ruWasmDescribe(value,depth){try{depth=depth||0;if(value===null)return{type:"null",value:null};var valueType=typeof value;if(valueType==="undefined")return{type:"undefined"};if(valueType==="number"||valueType==="boolean")return{type:valueType,value:value};if(valueType==="string")return{type:"string",length:value.length,value:value.length>200?value.slice(0,200):value};if(valueType==="function"){var text="";try{text=Function.prototype.toString.call(value)}catch(_){text=String(value)}return{type:"function",name:value.name||"",string:text.slice(0,160)}}if(ArrayBuffer.isView(value)){var preview=[];try{preview=Array.from(value.slice?value.slice(0,16):value).slice(0,16)}catch(_){}return{type:value.constructor&&value.constructor.name||"TypedArray",length:value.length,preview:preview}}if(Array.isArray(value)){return{type:"Array",length:value.length,preview:depth>0?undefined:value.slice(0,8).map(function(item){return __ruWasmDescribe(item,depth+1)})}}if(value&&typeof value.then==="function")return{type:"Promise"};var tag=Object.prototype.toString.call(value);var out={type:tag,constructorName:value&&value.constructor&&value.constructor.name};["kind","label","deviceId","groupId","state","matches","media","name","filename","description","suffixes","length","value","id","tagName","nodeName"].forEach(function(key){try{var item=value[key];if(typeof item==="string"||typeof item==="number"||typeof item==="boolean"||item===null)out[key]=item}catch(_){}});try{var keys=Object.keys(value);if(keys&&keys.length)out.keys=keys.slice(0,12)}catch(_){}return out}catch(error){return{type:typeof value,error:error&&error.message?error.message:String(error)}}}__ruWasmRecord("heap-trace-installed",{});`;
    if (!source.includes(preambleNeedle)) throw new Error('wasm.js strict-mode signature changed');
    source = source.replace(preambleNeedle, preambleReplacement);
    const replacements = [
      [
        `function i(n){var e,t=c(n);return(e=n)<36||(_[e]=r,r=e),t}`,
        `function i(n){var e,t=c(n);return __ruWasmRecord("heap-drop",{handle:n,value:__ruWasmDescribe(t)}),(e=n)<36||(_[e]=r,r=e),t}`,
        'drop-ref',
      ],
      [
        `function l(n){r===_.length&&_.push(_.length+1);var e=r;return r=_[e],_[e]=n,e}`,
        `function l(n){r===_.length&&_.push(_.length+1);var e=r;return r=_[e],_[e]=n,__ruWasmRecord("heap-set",{handle:e,value:__ruWasmDescribe(n)}),e}`,
        'heap-set',
      ],
      [
        `__wbg_push_446cc0334a2426e8=function(n,e){return c(n).push(c(e))}`,
        `__wbg_push_446cc0334a2426e8=function(n,e){var t=c(n),_=c(e),r=t.push(_);return __ruWasmRecord("array-push",{arrayHandle:n,valueHandle:e,value:__ruWasmDescribe(_),array:__ruWasmDescribe(t),result:r}),r}`,
        'array-push',
      ],
      [
        `__wbg_join_b6efd1e111c0dd52=function(n,e,t){return l(c(n).join(w(e,t)))}`,
        `__wbg_join_b6efd1e111c0dd52=function(n,e,t){var _=c(n),r=w(e,t),i=_.join(r);return __ruWasmRecord("array-join",{arrayHandle:n,array:__ruWasmDescribe(_),separator:r,result:i}),l(i)}`,
        'array-join',
      ],
      [
        `__wbg_all_f7b6ae27de68967a=function(n){return l(Promise.all(c(n)))}`,
        `__wbg_all_f7b6ae27de68967a=function(n){var e=c(n);return __ruWasmRecord("promise-all",{arrayHandle:n,array:__ruWasmDescribe(e)}),l(Promise.all(e))}`,
        'promise-all',
      ],
      [
        `__wbg_catch_cf98b11ab7c29a4e=function(n,e){return l(c(n).catch(c(e)))}`,
        `__wbg_catch_cf98b11ab7c29a4e=function(n,e){var t=c(n),_=c(e);return __ruWasmRecord("promise-catch",{promiseHandle:n,callbackHandle:e,promise:__ruWasmDescribe(t),callback:__ruWasmDescribe(_)}),l(t.catch(_))}`,
        'promise-catch',
      ],
      [
        `__wbg_then_b6fef331fde5cf0a=function(n,e){return l(c(n).then(c(e)))}`,
        `__wbg_then_b6fef331fde5cf0a=function(n,e){var t=c(n),_=c(e);return __ruWasmRecord("promise-then",{promiseHandle:n,callbackHandle:e,promise:__ruWasmDescribe(t),callback:__ruWasmDescribe(_)}),l(t.then(_))}`,
        'promise-then',
      ],
      [
        `__wbg_finally_fff9b79028420a96=function(n,e){return l(c(n).finally(c(e)))}`,
        `__wbg_finally_fff9b79028420a96=function(n,e){var t=c(n),_=c(e);return __ruWasmRecord("promise-finally",{promiseHandle:n,callbackHandle:e,promise:__ruWasmDescribe(t),callback:__ruWasmDescribe(_)}),l(t.finally(_))}`,
        'promise-finally',
      ],
      [
        `__wbg_set_8d5fd23e838df6b0=function(n,e,t){try{return Reflect.set(c(n),c(e),c(t))}catch(n){v(n)}}`,
        `__wbg_set_8d5fd23e838df6b0=function(n,e,t){try{var _=c(n),r=c(e),i=c(t),o=Reflect.set(_,r,i);return __ruWasmRecord("reflect-set",{targetHandle:n,keyHandle:e,valueHandle:t,key:__ruWasmDescribe(r),value:__ruWasmDescribe(i),target:__ruWasmDescribe(_),result:o}),o}catch(n){v(n)}}`,
        'reflect-set',
      ],
      [
        `function _(){r.cnt++;var n,e,t=r.a;r.a=0;try{return n=t,e=r.b,void b._dyn_core__ops__function__FnMut_____Output___R_as_wasm_bindgen__closure__WasmClosure___describe__invoke__h5c9b8cfcb2588a53(n,e)}finally{0==--r.cnt?b.__wbindgen_export_2.get(255)(t,r.b):r.a=t}}`,
        `function _(){r.cnt++;var n,e,t=r.a;r.a=0;try{return __ruWasmRecord("closure-call",{kind:"wrapper462",a:t,b:r.b,args:[]}),n=t,e=r.b,void b._dyn_core__ops__function__FnMut_____Output___R_as_wasm_bindgen__closure__WasmClosure___describe__invoke__h5c9b8cfcb2588a53(n,e)}finally{0==--r.cnt?b.__wbindgen_export_2.get(255)(t,r.b):r.a=t}}`,
        'closure-wrapper462',
      ],
      [
        `function _(n){i.cnt++;var e,t,_,r=i.a;i.a=0;try{return e=r,t=i.b,_=n,void b._dyn_core__ops__function__FnMut__A____Output___R_as_wasm_bindgen__closure__WasmClosure___describe__invoke__h93011b86c70ce711(e,t,l(_))}finally{0==--i.cnt?b.__wbindgen_export_2.get(257)(r,i.b):i.a=r}}`,
        `function _(n){i.cnt++;var e,t,_,r=i.a;i.a=0;try{return __ruWasmRecord("closure-call",{kind:"wrapper460",a:r,b:i.b,args:[__ruWasmDescribe(n)]}),e=r,t=i.b,_=n,void b._dyn_core__ops__function__FnMut__A____Output___R_as_wasm_bindgen__closure__WasmClosure___describe__invoke__h93011b86c70ce711(e,t,l(_))}finally{0==--i.cnt?b.__wbindgen_export_2.get(257)(r,i.b):i.a=r}}`,
        'closure-wrapper460',
      ],
    ];
    for (const [needle, replacement, label] of replacements) {
      if (!source.includes(needle)) throw new Error('wasm.js heap trace signature changed: ' + label);
      source = source.replace(needle, replacement);
    }
    return source;
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
  installWasmImportTrace();
  if (heapTraceEnabled) {
    window.__ruWasmHeapTrace = wasmHeapTrace;
    window.__ruWasmHeapTraceSeq__ = 0;
    window.__ruWasmHeapTraceLimit = 200000;
    const wasmJsUrl = '/Wasm/api/v1/wasm.js?_=' + Date.now();
    const wasmJsResponse = await fetch(wasmJsUrl, { cache: 'no-store' });
    if (!wasmJsResponse.ok) throw new Error('wasm.js fetch failed: ' + wasmJsResponse.status);
    (0, eval)(instrumentWasmRuntimeSource(await wasmJsResponse.text()));
  } else if (!window.wasm) {
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
    wasmTrace: traceEnabled ? wasmTrace : null,
    wasmImportTrace: importTraceEnabled ? wasmImportTrace : null,
    wasmHeapTrace: heapTraceEnabled ? wasmHeapTrace : null
  };
})()
"""
    expression = expression.replace("__TRACE_WASM__", "true" if trace_wasm else "false")
    expression = expression.replace("__TRACE_WASM_IMPORTS__", "true" if trace_wasm_imports else "false")
    expression = expression.replace("__TRACE_WASM_HEAP__", "true" if trace_wasm_heap else "false")
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
    parser.add_argument("--trace-wasm-imports", action="store_true")
    parser.add_argument("--trace-wasm-heap", action="store_true")
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
            cookie_info = generate_cookies_in_page(
                client,
                trace_wasm=args.trace_wasm,
                trace_wasm_imports=args.trace_wasm_imports,
                trace_wasm_heap=args.trace_wasm_heap,
            )
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
            "wasmImportTrace": cookie_info.get("wasmImportTrace"),
            "wasmHeapTrace": cookie_info.get("wasmHeapTrace"),
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
