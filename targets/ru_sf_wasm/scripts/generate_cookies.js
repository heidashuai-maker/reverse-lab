const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DEFAULT_UA =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

function parseArgs(argv) {
    const args = {
        ua: DEFAULT_UA,
        pretty: false,
        traceEnv: false,
    };

    for (let index = 2; index < argv.length; index += 1) {
        const item = argv[index];
        if (item === "--ua") {
            args.ua = argv[index + 1] || args.ua;
            index += 1;
        } else if (item === "--pretty") {
            args.pretty = true;
        } else if (item === "--trace-env") {
            args.traceEnv = true;
        }
    }

    return args;
}

function constructorForFlag(flag) {
    function BrowserConstructor() {
    }
    const constructorNames = {
        __isWindow: "Window",
        __node: "Node",
        __element: "Element",
        __htmlElement: "HTMLElement",
        __canvas: "HTMLCanvasElement",
        __iframe: "HTMLIFrameElement",
        __input: "HTMLInputElement",
        __webgl: "WebGLRenderingContext",
    };
    markNative(BrowserConstructor, constructorNames[flag] || "Object");

    Object.defineProperty(BrowserConstructor, Symbol.hasInstance, {
        value(object) {
            return Boolean(object && object[flag] === true);
        },
    });

    return BrowserConstructor;
}

function defineGlobal(name, value) {
    Object.defineProperty(global, name, {
        value,
        configurable: true,
        writable: true,
    });
}

const nativeFunctionNames = new WeakMap();
const originalFunctionToString = Function.prototype.toString;

function markNative(fn, name) {
    if (typeof fn === "function") {
        nativeFunctionNames.set(fn, name || fn.name || "");
    }
    return fn;
}

function installNativeToString() {
    if (Function.prototype.toString.__nativePatched) {
        return;
    }
    const nativeToString = function toString() {
        if (nativeFunctionNames.has(this)) {
            return `function ${nativeFunctionNames.get(this)}() { [native code] }`;
        }
        return originalFunctionToString.call(this);
    };
    Object.defineProperty(nativeToString, "__nativePatched", {value: true});
    Object.defineProperty(Function.prototype, "toString", {
        value: nativeToString,
        configurable: true,
        writable: true,
    });
}

function makeNativeFunction(name, impl) {
    const holder = {
        [name]: function (...args) {
            return impl.apply(this, args);
        },
    };
    return markNative(holder[name], name);
}

function definePrototypeGetter(prototype, name, getter) {
    Object.defineProperty(prototype, name, {
        get: markNative(getter, `get ${name}`),
        enumerable: true,
        configurable: true,
    });
}

function makeCookieJar() {
    const cookies = new Map();

    return {
        get(name) {
            return cookies.get(name);
        },
        all() {
            return Object.fromEntries(cookies);
        },
        header() {
            return Array.from(cookies, ([key, value]) => `${key}=${value}`).join("; ");
        },
        set(raw) {
            const first = String(raw).split(";")[0];
            const equalsIndex = first.indexOf("=");
            if (equalsIndex < 0) {
                return;
            }

            const name = first.slice(0, equalsIndex).trim();
            const value = first.slice(equalsIndex + 1).trim();
            if (name) {
                cookies.set(name, value);
            }
        },
    };
}

class NodeStub {
    constructor(tagName = "node") {
        this.__node = true;
        this.__element = true;
        this.__htmlElement = true;
        this.tagName = tagName.toUpperCase();
        this.nodeName = this.tagName;
        this.children = [];
        this.style = {};
        this.attributes = {};
        this.parentNode = null;
        this.className = "";
        this.id = "";
        this.innerHTML = "";
        this.textContent = "";
        this.value = "";
        this.clientWidth = 128;
        this.clientHeight = 64;
    }

    appendChild(node) {
        if (node) {
            node.parentNode = this;
            this.children.push(node);
        }
        return node;
    }

    removeChild(node) {
        this.children = this.children.filter((child) => child !== node);
        if (node) {
            node.parentNode = null;
        }
        return node;
    }

    setAttribute(name, value) {
        this.attributes[name] = String(value);
        if (name === "id") {
            this.id = String(value);
        }
        if (name === "class") {
            this.className = String(value);
        }
    }

    getAttribute(name) {
        return this.attributes[name] ?? null;
    }

    hasAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this.attributes, name);
    }

    get offsetHeight() {
        return this.clientHeight;
    }

    get offsetWidth() {
        return this.clientWidth;
    }

    canPlayType(mediaType = "") {
        const normalized = String(mediaType).toLowerCase();
        if (this.tagName === "VIDEO") {
            if (normalized.includes("ogg")) {
                return "";
            }
            if (normalized.includes("h264") || normalized.includes("avc1") || normalized.includes("webm")) {
                return "probably";
            }
            return "";
        }
        if (this.tagName === "AUDIO") {
            if (normalized.includes("x-m4a") || normalized.includes("mp4")) {
                return "maybe";
            }
            if (normalized.includes("mpeg") || normalized.includes("mp3") || normalized.includes("wav") || normalized.includes("ogg") || normalized.includes("aac")) {
                return "probably";
            }
            return "";
        }
        return "";
    }
}

class WebGLStub {
    constructor() {
        this.__webgl = true;
        this.VENDOR = 7936;
        this.RENDERER = 7937;
        this.VERSION = 7938;
        this.SHADING_LANGUAGE_VERSION = 35724;
        this.ARRAY_BUFFER = 34962;
        this.STATIC_DRAW = 35044;
    }

    getExtension(name) {
        if (name === "WEBGL_debug_renderer_info") {
            return {
                UNMASKED_VENDOR_WEBGL: 37445,
                UNMASKED_RENDERER_WEBGL: 37446,
            };
        }
        if (name === "WEBGL_lose_context") {
            return {
                loseContext() {
                }
            };
        }
        return null;
    }

    getParameter(parameter) {
        const values = {
            7936: "WebKit",
            7937: "WebKit WebGL",
            7938: "WebGL 1.0 (OpenGL ES 2.0 Chromium)",
            35724: "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)",
            37445: "Google Inc. (Microsoft)",
            37446: "ANGLE (Microsoft, Microsoft Basic Render Driver (0x0000008C) Direct3D11 vs_5_0 ps_5_0, D3D11)",
        };
        return values[parameter] ?? 0;
    }

    getSupportedExtensions() {
        return [
            "ANGLE_instanced_arrays",
            "EXT_blend_minmax",
            "EXT_clip_control",
            "EXT_color_buffer_half_float",
            "EXT_depth_clamp",
            "EXT_float_blend",
            "EXT_frag_depth",
            "EXT_polygon_offset_clamp",
            "EXT_shader_texture_lod",
            "EXT_texture_compression_bptc",
            "EXT_texture_compression_rgtc",
            "EXT_texture_filter_anisotropic",
            "EXT_texture_mirror_clamp_to_edge",
            "EXT_sRGB",
            "KHR_parallel_shader_compile",
            "OES_element_index_uint",
            "OES_fbo_render_mipmap",
            "OES_standard_derivatives",
            "OES_texture_float",
            "OES_texture_float_linear",
            "OES_texture_half_float",
            "OES_texture_half_float_linear",
            "OES_vertex_array_object",
            "WEBGL_blend_func_extended",
            "WEBGL_color_buffer_float",
            "WEBGL_compressed_texture_s3tc",
            "WEBGL_compressed_texture_s3tc_srgb",
            "WEBGL_debug_renderer_info",
            "WEBGL_debug_shaders",
            "WEBGL_depth_texture",
            "WEBGL_draw_buffers",
            "WEBGL_lose_context",
            "WEBGL_multi_draw",
            "WEBGL_polygon_mode",
        ];
    }

    createBuffer() {
        return {};
    }

    bindBuffer() {
    }

    bufferData() {
    }

    createProgram() {
        return {};
    }

    createShader() {
        return {};
    }

    shaderSource() {
    }

    compileShader() {
    }

    attachShader() {
    }

    linkProgram() {
    }

    useProgram() {
    }

    getAttribLocation() {
        return 0;
    }

    getUniformLocation() {
        return {};
    }

    enableVertexAttribArray() {
    }

    vertexAttribPointer() {
    }

    uniform2f() {
    }

    drawArrays() {
    }

    getShaderParameter() {
        return true;
    }

    getProgramParameter() {
        return true;
    }

    getShaderInfoLog() {
        return "";
    }

    getProgramInfoLog() {
        return "";
    }

    deleteShader() {
    }

    deleteProgram() {
    }
}

class Canvas2DStub {
    constructor(canvas) {
        this.canvas = canvas;
        this.fillStyle = "";
        this.strokeStyle = "";
        this.font = "";
        this.textBaseline = "";
        this._pixel = [0, 0, 0, 0];
    }

    fillRect(x, y) {
        if (Number(x) === 0 && Number(y) === 0) {
            this._pixel = [255, 102, 0, 255];
        }
    }

    clearRect() {
    }

    fillText() {
    }

    strokeText() {
    }

    arc() {
    }

    fill() {
    }

    stroke() {
    }

    beginPath() {
    }

    closePath() {
    }

    rect() {
    }

    moveTo() {
    }

    lineTo() {
    }

    drawImage(image) {
        this._pixel = image && image._transparentPixel ? [0, 0, 0, 0] : [0, 0, 0, 255];
    }

    isPointInPath() {
        return false;
    }

    getImageData() {
        return {
            data: new Uint8ClampedArray(this._pixel),
            width: 1,
            height: 1,
        };
    }

    measureText(text) {
        return {
            width: String(text).length * 7,
            actualBoundingBoxAscent: 8,
            actualBoundingBoxDescent: 2,
        };
    }

    createLinearGradient() {
        return {
            addColorStop() {
            }
        };
    }
}

class CanvasStub extends NodeStub {
    constructor() {
        super("canvas");
        this.__canvas = true;
        this.width = 300;
        this.height = 150;
    }

    getContext(kind) {
        if (kind === "2d") {
            return new Canvas2DStub(this);
        }
        if (String(kind).includes("webgl")) {
            return new WebGLStub();
        }
        return null;
    }

    toDataURL() {
        return "data:image/png;base64,iVBORw0KGgo=";
    }
}

class IFrameStub extends NodeStub {
    constructor() {
        super("iframe");
        this.__iframe = true;
        this._srcdoc = "";
        this.contentWindow = global;
    }

    set srcdoc(value) {
        this._srcdoc = value;
    }

    get srcdoc() {
        return this._srcdoc;
    }
}

class InputStub extends NodeStub {
    constructor() {
        super("input");
        this.__input = true;
        this.value = "";
    }
}

function findById(node, id) {
    if (!node) {
        return null;
    }
    if (node.id === id) {
        return node;
    }
    for (const child of node.children || []) {
        const found = findById(child, id);
        if (found) {
            return found;
        }
    }
    return null;
}

class DocumentStub extends NodeStub {
    constructor(cookieJar) {
        super("#document");
        this.__document = true;
        this.body = new NodeStub("body");
        this.documentElement = new NodeStub("html");
        this.body.clientWidth = 1349;
        this.body.clientHeight = 749;
        this.documentElement.clientWidth = 1349;
        this.documentElement.clientHeight = 749;
        this.baseURI = "https://kad.arbitr.ru/";
        this.currentScript = {
            src: "https://kad.arbitr.ru/Wasm/api/v1/wasm.js",
        };

        Object.defineProperty(this, "cookie", {
            get: () => cookieJar.header(),
            set: (raw) => cookieJar.set(raw),
        });
    }

    createElement(tagName) {
        const tag = String(tagName).toLowerCase();
        if (tag === "canvas") {
            return new CanvasStub();
        }
        if (tag === "iframe") {
            return new IFrameStub();
        }
        if (tag === "input") {
            return new InputStub();
        }
        return new NodeStub(tag);
    }

    createEvent(type) {
        if (String(type).toLowerCase() === "touchevent") {
            throw new Error("The provided event type ('TouchEvent') is invalid.");
        }
        return {
            type,
            initEvent() {
            },
            initMouseEvent() {
            },
        };
    }

    getElementById(id) {
        const normalized = String(id);
        return (
            findById(this.body, normalized) ||
            findById(this.documentElement, normalized)
        );
    }

    getElementsByClassName(name) {
        return name === "adsbox" ? [new NodeStub("div")] : [];
    }

    getElementsByTagName(name) {
        const normalized = String(name).toLowerCase();
        if (normalized === "body") {
            return [this.body];
        }
        if (normalized === "html") {
            return [this.documentElement];
        }
        return [];
    }

    querySelector() {
        return null;
    }

    querySelectorAll() {
        return [];
    }
}

class ImageStub {
    constructor() {
        this.width = 0;
        this.height = 0;
        this.complete = false;
        this._transparentPixel = false;
    }

    set src(value) {
        this._src = value;
        this.complete = true;
        this._transparentPixel = String(value).includes("V2NgAAIAAAUAAarVyFE");
        setTimeout(() => {
            if (this.onload) {
                this.onload();
            }
        }, 0);
    }

    get src() {
        return this._src;
    }
}
markNative(ImageStub, "Image");

function WebSocketStub(url) {
    if (!(this instanceof WebSocketStub)) {
        throw new TypeError("Failed to construct 'WebSocket': Please use the 'new' operator, this DOM object constructor cannot be called as a function.");
    }
    this.url = String(url || "");
    this.readyState = WebSocketStub.CONNECTING;
    setTimeout(() => {
        this.readyState = WebSocketStub.CLOSED;
        if (typeof this.onerror === "function") {
            this.onerror(new EventStub("error"));
        }
        if (typeof this.onclose === "function") {
            this.onclose(new EventStub("close"));
        }
    }, 0);
}
WebSocketStub.CONNECTING = 0;
WebSocketStub.OPEN = 1;
WebSocketStub.CLOSING = 2;
WebSocketStub.CLOSED = 3;
WebSocketStub.prototype.close = markNative(function close() {
    this.readyState = WebSocketStub.CLOSED;
}, "close");
WebSocketStub.prototype.send = markNative(function send() {
}, "send");
markNative(WebSocketStub, "WebSocket");

class EventStub {
    constructor(type) {
        this.type = type;
    }
}

class StorageStub {
    constructor() {
        this._items = new Map();
    }

    get length() {
        return this._items.size;
    }

    key(index) {
        return Array.from(this._items.keys())[index] ?? null;
    }

    getItem(key) {
        const normalized = String(key);
        return this._items.has(normalized) ? this._items.get(normalized) : null;
    }

    setItem(key, value) {
        this._items.set(String(key), String(value));
    }

    removeItem(key) {
        this._items.delete(String(key));
    }

    clear() {
        this._items.clear();
    }
}
for (const method of ["key", "getItem", "setItem", "removeItem", "clear"]) {
    markNative(StorageStub.prototype[method], method);
}

class MimeTypeStub {
    constructor(type, suffixes, description) {
        this.type = type;
        this.suffixes = suffixes;
        this.description = description;
        this.enabledPlugin = null;
    }
}
Object.defineProperty(MimeTypeStub.prototype, Symbol.toStringTag, {value: "MimeType"});

class PluginStub {
    constructor(name, filename, description, mimeTypes) {
        this.name = name;
        this.filename = filename;
        this.description = description;
        this.length = mimeTypes.length;
        mimeTypes.forEach((mimeType, index) => {
            Object.defineProperty(this, index, {
                value: mimeType,
                enumerable: false,
                configurable: true,
            });
            mimeType.enabledPlugin = this;
        });
    }

    item(index) {
        return this[index] || null;
    }

    namedItem(name) {
        return Array.from({length: this.length}, (_, index) => this[index])
            .find((mimeType) => mimeType && mimeType.type === name) || null;
    }
}
markNative(PluginStub.prototype.item, "item");
markNative(PluginStub.prototype.namedItem, "namedItem");
Object.defineProperty(PluginStub.prototype, Symbol.toStringTag, {value: "Plugin"});

class PluginArrayStub {
    constructor(items) {
        this.length = items.length;
        items.forEach((plugin, index) => {
            Object.defineProperty(this, index, {
                value: plugin,
                enumerable: false,
                configurable: true,
            });
            Object.defineProperty(this, plugin.name, {
                value: plugin,
                enumerable: false,
                configurable: true,
            });
        });
    }

    item(index) {
        return this[index] || null;
    }

    namedItem(name) {
        return this[name] || null;
    }

    refresh() {
    }

    [Symbol.iterator]() {
        return Array.from({length: this.length}, (_, index) => this[index])[Symbol.iterator]();
    }
}
for (const method of ["item", "namedItem", "refresh"]) {
    markNative(PluginArrayStub.prototype[method], method);
}
Object.defineProperty(PluginArrayStub.prototype, Symbol.toStringTag, {value: "PluginArray"});

class MimeTypeArrayStub {
    constructor(items) {
        this.length = items.length;
        items.forEach((mimeType, index) => {
            Object.defineProperty(this, index, {
                value: mimeType,
                enumerable: false,
                configurable: true,
            });
            Object.defineProperty(this, mimeType.type, {
                value: mimeType,
                enumerable: false,
                configurable: true,
            });
        });
    }

    item(index) {
        return this[index] || null;
    }

    namedItem(name) {
        return this[name] || null;
    }

    [Symbol.iterator]() {
        return Array.from({length: this.length}, (_, index) => this[index])[Symbol.iterator]();
    }
}
for (const method of ["item", "namedItem"]) {
    markNative(MimeTypeArrayStub.prototype[method], method);
}
Object.defineProperty(MimeTypeArrayStub.prototype, Symbol.toStringTag, {value: "MimeTypeArray"});

function makePluginCollections() {
    const mimeTypes = [
        new MimeTypeStub("application/pdf", "pdf", "Portable Document Format"),
        new MimeTypeStub("text/pdf", "pdf", "Portable Document Format"),
    ];
    const pluginNames = [
        "PDF Viewer",
        "Chrome PDF Viewer",
        "Chromium PDF Viewer",
        "Microsoft Edge PDF Viewer",
        "WebKit built-in PDF",
    ];
    const plugins = pluginNames.map((name) =>
        new PluginStub(name, "internal-pdf-viewer", "Portable Document Format", mimeTypes)
    );
    return {
        plugins: new PluginArrayStub(plugins),
        mimeTypes: new MimeTypeArrayStub(mimeTypes),
    };
}

const navigatorState = new WeakMap();
class NavigatorStub {
}
delete NavigatorStub.prototype.constructor;

function navigatorGetter(name, value) {
    definePrototypeGetter(NavigatorStub.prototype, name, function () {
        const state = navigatorState.get(this) || {};
        return Object.prototype.hasOwnProperty.call(state, name) ? state[name] : value;
    });
}

function navigatorMethod(name, impl) {
    NavigatorStub.prototype[name] = markNative(function (...args) {
        return impl.apply(this, args);
    }, name);
}

[
    ["vendorSub", ""],
    ["productSub", "20030107"],
    ["vendor", "Google Inc."],
    ["maxTouchPoints", 0],
    ["scheduling", {}],
    ["userActivation", {}],
    ["geolocation", {}],
    ["doNotTrack", null],
    ["webkitTemporaryStorage", {}],
    ["webkitPersistentStorage", {}],
    ["windowControlsOverlay", {}],
    ["hardwareConcurrency", 12],
    ["cookieEnabled", true],
    ["appCodeName", "Mozilla"],
    ["appName", "Netscape"],
    ["appVersion", undefined],
    ["platform", "Win32"],
    ["product", "Gecko"],
    ["userAgent", undefined],
    ["language", "ru-RU"],
    ["languages", undefined],
    ["onLine", true],
    ["webdriver", false],
    ["plugins", undefined],
    ["mimeTypes", undefined],
    ["pdfViewerEnabled", true],
    ["connection", {}],
].forEach(([name, value]) => navigatorGetter(name, value));
navigatorMethod("getGamepads", () => []);
navigatorMethod("javaEnabled", () => false);
navigatorMethod("sendBeacon", () => true);
navigatorMethod("vibrate", () => false);
Object.defineProperty(NavigatorStub.prototype, "constructor", {
    value: markNative(function Navigator() {
    }, "Navigator"),
    writable: true,
    configurable: true,
});
[
    ["deprecatedRunAdAuctionEnforcesKAnonymity", {}],
    ["protectedAudience", {}],
].forEach(([name, value]) => navigatorGetter(name, value));
[
    ["bluetooth", {}],
    ["clipboard", {}],
    ["credentials", {}],
    ["keyboard", {}],
    ["managed", {}],
    ["mediaDevices", undefined],
    ["serviceWorker", {}],
    ["virtualKeyboard", {}],
    ["wakeLock", {}],
    ["deviceMemory", 32],
    ["userAgentData", undefined],
    ["locks", {}],
    ["storage", {}],
    ["gpu", {}],
    ["login", {}],
    ["ink", {}],
    ["mediaCapabilities", {}],
    ["permissions", undefined],
    ["devicePosture", {}],
    ["hid", {}],
    ["mediaSession", {}],
    ["presentation", {}],
    ["serial", {}],
    ["usb", {}],
    ["xr", {}],
    ["storageBuckets", {}],
].forEach(([name, value]) => navigatorGetter(name, value));
[
    "adAuctionComponents",
    "runAdAuction",
    "canLoadAdAuctionFencedFrame",
    "canShare",
    "share",
    "clearAppBadge",
].forEach((name) => navigatorMethod(name, () => false));
navigatorMethod("getBattery", () =>
    Promise.resolve({
        charging: true,
        chargingTime: 0,
        dischargingTime: Infinity,
        level: 1,
    })
);
[
    "getUserMedia",
    "requestMIDIAccess",
    "requestMediaKeySystemAccess",
    "setAppBadge",
    "webkitGetUserMedia",
    "clearOriginJoinedAdInterestGroups",
    "createAuctionNonce",
    "joinAdInterestGroup",
    "leaveAdInterestGroup",
    "updateAdInterestGroups",
    "deprecatedReplaceInURN",
    "deprecatedURNToURL",
    "getInstalledRelatedApps",
    "getInterestGroupAdAuctionData",
    "registerProtocolHandler",
    "unregisterProtocolHandler",
].forEach((name) => navigatorMethod(name, () => Promise.resolve(null)));
Object.defineProperty(NavigatorStub.prototype, Symbol.toStringTag, {value: "Navigator"});

const screenState = new WeakMap();
class ScreenStub {
}
[
    ["availWidth", 800],
    ["availHeight", 600],
    ["width", 800],
    ["height", 600],
    ["colorDepth", 24],
    ["pixelDepth", 24],
    ["availLeft", 0],
    ["availTop", 0],
    ["isExtended", false],
].forEach(([name, value]) => {
    definePrototypeGetter(ScreenStub.prototype, name, function () {
        const state = screenState.get(this) || {};
        return Object.prototype.hasOwnProperty.call(state, name) ? state[name] : value;
    });
});
Object.defineProperty(ScreenStub.prototype, Symbol.toStringTag, {value: "Screen"});

function makeUAParser(userAgent) {
    const chromeMatch = String(userAgent).match(/(?:Chrome|Chromium)\/([0-9.]+)/);
    const chromeVersion = chromeMatch ? chromeMatch[1] : "120.0.0.0";
    const chromeMajor = chromeVersion.split(".")[0] || "120";

    function result() {
        const parsed = {
            ua: userAgent,
            browser: {name: "Chrome", version: chromeVersion, major: chromeMajor},
            device: {vendor: undefined, model: undefined, type: undefined},
            os: {name: "Windows", version: "10"},
            engine: {name: "Blink", version: chromeMajor},
            cpu: {architecture: "amd64"},
        };

        parsed.getResult = () => parsed;
        parsed.getBrowser = () => parsed.browser;
        parsed.getDevice = () => parsed.device;
        parsed.getOS = () => parsed.os;
        parsed.getEngine = () => parsed.engine;
        parsed.getCPU = () => parsed.cpu;
        parsed.getUA = () => parsed.ua;
        return parsed;
    }

    const UAParserStub = function UAParserStub() {
        return result();
    };

    Object.assign(UAParserStub.prototype, {
        getResult: result,
        getBrowser: () => result().browser,
        getDevice: () => result().device,
        getOS: () => result().os,
        getEngine: () => result().engine,
        getCPU: () => result().cpu,
        getUA: () => userAgent,
    });

    return UAParserStub;
}

function matchMediaQuery(query, screen) {
    const normalized = String(query).toLowerCase();
    const viewportWidth = Number(global.innerWidth || screen.width);
    const viewportHeight = Number(global.innerHeight || screen.height);
    const tests = [
        [/min-width:\s*(\d+)px/, (value) => viewportWidth >= value],
        [/max-width:\s*(\d+)px/, (value) => viewportWidth <= value],
        [/min-height:\s*(\d+)px/, (value) => viewportHeight >= value],
        [/max-height:\s*(\d+)px/, (value) => viewportHeight <= value],
        [/min-device-width:\s*(\d+)px/, (value) => screen.width >= value],
        [/max-device-width:\s*(\d+)px/, (value) => screen.width <= value],
        [/device-width:\s*(\d+)px/, (value) => screen.width === value],
        [/min-device-height:\s*(\d+)px/, (value) => screen.height >= value],
        [/max-device-height:\s*(\d+)px/, (value) => screen.height <= value],
        [/device-height:\s*(\d+)px/, (value) => screen.height === value],
        [/color-gamut:\s*srgb/, () => true],
        [/prefers-reduced-motion:\s*no-preference/, () => true],
        [/pointer:\s*fine/, () => true],
        [/hover:\s*hover/, () => true],
    ];
    for (const [pattern, predicate] of tests) {
        const match = normalized.match(pattern);
        if (match) {
            return predicate(Number(match[1]));
        }
    }
    return false;
}

function describeTraceValue(value) {
    if (value === null) {
        return "null";
    }
    if (typeof value === "undefined") {
        return "undefined";
    }
    if (typeof value === "string") {
        return JSON.stringify(value.length > 120 ? `${value.slice(0, 117)}...` : value);
    }
    if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
    }
    if (Array.isArray(value)) {
        return JSON.stringify(value);
    }
    if (ArrayBuffer.isView(value)) {
        return `${value.constructor.name}[${Array.from(value).join(",")}]`;
    }
    try {
        return `${Object.prototype.toString.call(value)} ${JSON.stringify(value)}`;
    } catch (error) {
        return Object.prototype.toString.call(value);
    }
}

function installEnvironmentTrace() {
    const trace = [];
    const originalReflectSet = Reflect.set;
    Reflect.set = markNative(function set(target, key, value, receiver) {
        if (typeof key === "string") {
            trace.push([key, describeTraceValue(value)]);
        }
        if (arguments.length >= 4) {
            return originalReflectSet(target, key, value, receiver);
        }
        return originalReflectSet(target, key, value);
    }, "set");
    return trace;
}

function normalizeWasmRuntimeSource(source) {
    const overflowProbe = '__wbg_resoverflow_3101caf8eda0c7cd=function(){var e,t,_,r;return l((_=t="",r=e=0,function n(){try{e++,n()}catch(n){t=n.message,_=n.name,r=n.stack.toString().length}}(),{depth:e,errorMessage:t,errorName:_,errorStacklength:r}))}';
    const chromeLikeOverflow = '__wbg_resoverflow_3101caf8eda0c7cd=function(){return l({depth:8850,errorMessage:"Maximum call stack size exceeded",errorName:"RangeError",errorStacklength:738})}';
    if (!source.includes(overflowProbe)) {
        throw new Error("wasm.js resOverflow probe signature changed");
    }
    return source.replace(overflowProbe, chromeLikeOverflow);
}

function installBrowserEnvironment(userAgent, cookieJar) {
    installNativeToString();
    const document = new DocumentStub(cookieJar);
    const pluginCollections = makePluginCollections();

    const permissions = {
        query: markNative(function query() {
            return Promise.resolve({
                state: "prompt",
                onchange: null,
            });
        }, "query"),
    };
    Object.defineProperty(permissions, Symbol.toStringTag, {value: "Permissions"});

    const mediaDevices = {
        enumerateDevices: markNative(function enumerateDevices() {
            return Promise.resolve([
                {
                    deviceId: "",
                    groupId: "",
                    kind: "audiooutput",
                    label: "",
                },
            ]);
        }, "enumerateDevices"),
    };
    Object.defineProperty(mediaDevices, Symbol.toStringTag, {value: "MediaDevices"});

    const navigator = Object.create(NavigatorStub.prototype);
    navigatorState.set(navigator, {
        userAgent,
        appVersion: userAgent.replace(/^Mozilla\//, ""),
        languages: ["ru-RU", "ru", "en-US", "en"],
        plugins: pluginCollections.plugins,
        mimeTypes: pluginCollections.mimeTypes,
        permissions,
        mediaDevices,
    });

    const screen = Object.create(ScreenStub.prototype);
    screenState.set(screen, {
        width: 800,
        height: 600,
        availWidth: 800,
        availHeight: 600,
        colorDepth: 24,
        pixelDepth: 24,
    });

    const runtimeConsole = Object.create(console);
    runtimeConsole.debug = () => {
    };
    markNative(runtimeConsole.debug, "debug");

    global.__isWindow = true;
    defineGlobal("window", global);
    defineGlobal("self", global);
    defineGlobal("globalThis", global);
    defineGlobal("console", runtimeConsole);
    defineGlobal("document", document);
    defineGlobal("navigator", navigator);
    defineGlobal("screen", screen);
    defineGlobal("location", {
        href: "https://kad.arbitr.ru/",
        protocol: "https:",
        hostname: "kad.arbitr.ru",
        host: "kad.arbitr.ru",
        origin: "https://kad.arbitr.ru",
        pathname: "/",
    });
    defineGlobal("innerWidth", 1349);
    defineGlobal("innerHeight", 749);
    defineGlobal("outerWidth", 1365);
    defineGlobal("outerHeight", 900);
    defineGlobal("pageXOffset", 0);
    defineGlobal("pageYOffset", 0);
    defineGlobal("screenX", 10);
    defineGlobal("screenY", 0);
    defineGlobal("devicePixelRatio", 1);
    defineGlobal("chrome", {
        app: {constructor: Object},
        csi: {constructor: Object},
        loadTimes: {constructor: Object},
    });
    defineGlobal("Notification", {permission: "default"});
    defineGlobal("external", {});
    defineGlobal("__matchMediaQueries", []);
    defineGlobal("UAParser", makeUAParser(userAgent));
    defineGlobal("eval", eval);
    const nodeSetTimeout = setTimeout;
    const nodeClearTimeout = clearTimeout;
    defineGlobal("setTimeout", markNative(function setTimeout(...args) {
        return nodeSetTimeout(...args);
    }, "setTimeout"));
    defineGlobal("clearTimeout", markNative(function clearTimeout(...args) {
        return nodeClearTimeout(...args);
    }, "clearTimeout"));
    defineGlobal("matchMedia", markNative(function matchMedia(query) {
        global.__matchMediaQueries.push(String(query));
        return ({
        matches: matchMediaQuery(query, screen),
        media: query,
        addListener: markNative(function addListener() {
        }, "addListener"),
        removeListener: markNative(function removeListener() {
        }, "removeListener"),
        addEventListener: markNative(function addEventListener() {
        }, "addEventListener"),
        removeEventListener: markNative(function removeEventListener() {
        }, "removeEventListener"),
        });
    }, "matchMedia"));
    defineGlobal("Window", constructorForFlag("__isWindow"));
    defineGlobal("Node", constructorForFlag("__node"));
    defineGlobal("Element", constructorForFlag("__element"));
    defineGlobal("HTMLElement", constructorForFlag("__htmlElement"));
    defineGlobal("HTMLCanvasElement", constructorForFlag("__canvas"));
    defineGlobal("HTMLIFrameElement", constructorForFlag("__iframe"));
    defineGlobal("HTMLInputElement", constructorForFlag("__input"));
    defineGlobal("WebGLRenderingContext", constructorForFlag("__webgl"));
    defineGlobal("Image", ImageStub);
    defineGlobal("WebSocket", WebSocketStub);
    defineGlobal("Event", EventStub);
    defineGlobal("localStorage", new StorageStub());
    defineGlobal("sessionStorage", new StorageStub());
    defineGlobal("indexedDB", {});
    defineGlobal("Request", undefined);
    defineGlobal("fetch", undefined);
}

async function main() {
    const args = parseArgs(process.argv);
    const cookieJar = makeCookieJar();
    const sourceDir = path.resolve(__dirname, "..", "source");

    const fpJs = fs.readFileSync(path.join(sourceDir, "fp.js"), "utf8");
    const fpWasm = fs.readFileSync(path.join(sourceDir, "fp_bg.wasm"));
    let wasmJs = fs.readFileSync(path.join(sourceDir, "wasm.js"), "utf8");
    const wasmWasm = fs.readFileSync(path.join(sourceDir, "wasm_bg.wasm"));
    wasmJs = normalizeWasmRuntimeSource(wasmJs);

    installBrowserEnvironment(args.ua, cookieJar);

    vm.runInThisContext(fpJs, {filename: path.join(sourceDir, "fp.js")});
    await fp.default(fpWasm);
    await fp.get();

    const wasmTrace = args.traceEnv ? installEnvironmentTrace() : null;

    vm.runInThisContext(wasmJs, {filename: path.join(sourceDir, "wasm.js")});
    await wasm.default(wasmWasm);
    wasm.main();

    await new Promise((resolve) => setTimeout(resolve, 600));

    const payload = {
        pr_fp: cookieJar.get("pr_fp"),
        wasm: cookieJar.get("wasm"),
        cookies: cookieJar.all(),
        cookieHeader: cookieJar.header(),
        userAgent: args.ua,
    };
    if (args.traceEnv) {
        payload.wasmTrace = wasmTrace;
        payload.matchMediaQueries = global.__matchMediaQueries;
    }

    if (!payload.pr_fp || !payload.wasm) {
        throw new Error(`cookie generation failed: ${JSON.stringify(payload.cookies)}`);
    }

    process.stdout.write(JSON.stringify(payload, null, args.pretty ? 2 : 0));
    process.stdout.write("\n");
}

main().catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exit(1);
});
