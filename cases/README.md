# Reverse Case Library

本目录存放已经验证、可复用、已脱敏的逆向经验案例。它不是目标原始材料目录，而是给后续相似目标做快速指纹匹配、路线选择和复现定位的经验库。

## 使用时机

在 `SKILL_ROUTER.md` 选出最窄 skill 之后、正式进入重建或补环境之前，先查本目录：

1. 从目标 URL、脚本名、请求参数、Cookie、响应状态、JS/WASM/Worker 关键字中提取技术指纹。
2. 在下方索引表或案例文件的“指纹检测规则”中匹配。
3. 命中后读取对应案例，优先复用其中的“已验证定位路径”“还原代码模板”“可验证事实清单”。
4. 未命中时按 `targets/<site>/` 完成一次完整分析，脱敏后沉淀为新 case。

## Artifact Boundary

- `targets/<site>/`: 保存目标站点原始 JS、HTML、WASM、字体、cookie、抓包、输出程序和中文 notes。
- `js_reverse_cache/`: 保存临时下载、一次性实验、未整理证据。
- `cases/`: 只保存脱敏后的通用结论、定位路径、代码骨架、踩坑和验证清单。

不要把真实域名、完整 URL、真实 Cookie、真实密钥、大段目标源码、未脱敏抓包写入 case。

## 目录组织

根目录只放总入口、通用模板和跨类型方法论骨架；具体还原方式或详细案例放进技术家族目录。

```text
cases/
├── README.md
├── _template.md
├── wasm-protocol-recovery-playbook.md
├── wasm/
│   └── wasm-bindgen-pr-fp-wasm-cookie-gate.md
├── vmp/
│   ├── universal-vmp-source-instrumentation.md
│   ├── jsvmp-xhr-interceptor-env-emulation.md
│   └── jsvmp-dual-sign-cacheopts-firefox.md
└── waf-cookie/
    └── rs6-cookie-412-sdenv.md
```

新增目录优先按技术家族或问题类型命名，例如 `wasm/`、`response-decode/`、`fingerprint/`、`captcha/`。不要按具体站点、域名或客户名建目录。

## 案例索引

| 案例文件 | 技术特征 | 首选路线 | 适用场景 |
| --- | --- | --- | --- |
| [_template.md](_template.md) | 通用案例模板 | - | 新增 case 时复制此文件 |
| [vmp/universal-vmp-source-instrumentation.md](vmp/universal-vmp-source-instrumentation.md) | 通用 VMP / while-switch / dispatch loop / hot keys | `find-crypto-entry` -> `env-patch` 或 `web-protocol-recovery` | 算法封装在虚拟机 dispatch 循环里，需源码级插桩学习入口和环境读取 |
| [vmp/jsvmp-xhr-interceptor-env-emulation.md](vmp/jsvmp-xhr-interceptor-env-emulation.md) | JSVMP + XHR 拦截器 + 单签名参数 + jsdom 环境伪装 | `find-crypto-entry` -> `env-patch` | 安全 SDK 通过 XHR open/send 拦截业务请求并追加签名 |
| [vmp/jsvmp-dual-sign-cacheopts-firefox.md](vmp/jsvmp-dual-sign-cacheopts-firefox.md) | JSVMP 双签名 + XHR/fetch 双通道 + cacheOpts + Firefox 指纹 | `find-crypto-entry` -> `env-patch` | 一个签名进 URL，另一个签名进 header，且路径注册依赖 cacheOpts |
| [waf-cookie/rs6-cookie-412-sdenv.md](waf-cookie/rs6-cookie-412-sdenv.md) | RS6 / 412 challenge / 动态 Cookie / sdenv | `rs-reverse` 或 `env-patch` | 首跳 412 返回挑战页，服务端 Cookie + 客户端 JS Cookie 共同放行 |
| [wasm-protocol-recovery-playbook.md](wasm-protocol-recovery-playbook.md) | WASM helper / WASM sign / WASM memory I/O | `web-protocol-recovery` 或 `find-crypto-entry` -> `web-protocol-recovery` | 签名、加密、解密或编码逻辑封装在 `.wasm` 中 |
| [wasm/wasm-bindgen-pr-fp-wasm-cookie-gate.md](wasm/wasm-bindgen-pr-fp-wasm-cookie-gate.md) | wasm-bindgen 双 Cookie / `pr_fp` + `wasm` / `__wbg_setcookie_*` | `web-protocol-recovery` | 指纹 WASM 生成 `pr_fp`，gate WASM 调用 `main()` 写入 `wasm` 后放行业务请求 |

## 指纹速查

| 命中特征 | 可能路线 | 建议读取 |
| --- | --- | --- |
| `while(true){switch(...)}` / dispatch loop / 大字节码数组 / 单 JS 100KB+ | VMP 源码级插桩 | `vmp/universal-vmp-source-instrumentation.md` |
| `webmssdk` / 安全 SDK glue / `byted_acrawler` / XHR 拦截器 / 单个长签名参数 | JSVMP 喂入-截出 + jsdom 环境伪装 | `vmp/jsvmp-xhr-interceptor-env-emulation.md` |
| `cacheOpts` / 双签名 / URL 参数 + header 同时变化 / XHR + fetch 都被改写 | 双通道签名恢复 | `vmp/jsvmp-dual-sign-cacheopts-firefox.md` |
| 首跳 412 / `$_ts` / 动态入口函数 / 服务端 S Cookie + 客户端 T Cookie | RS6 Cookie challenge | `waf-cookie/rs6-cookie-412-sdenv.md` |
| `.wasm` / `WebAssembly.instantiate` / `WebAssembly.Memory` / `wasm-bindgen` / `Module.cwrap` | WASM 协议恢复 | `wasm-protocol-recovery-playbook.md` |
| `pr_fp` + `wasm` 双 Cookie / `fp_bg.wasm` + `wasm_bg.wasm` / `__wbg_setcookie_*` / `wasm.main()` | wasm-bindgen Cookie gate | `wasm/wasm-bindgen-pr-fp-wasm-cookie-gate.md` |
| 固定长度 sign/token/header，JS 中只见 glue，看不到算法 | WASM、Worker 或 VMP 黑箱 | 先定位入口，再按命中特征选择具体 case |

## 参数特征速查

参数名、header 名、Cookie 名和输出长度是最高价值的路由信号。发现完全一致或高度相似时，优先读取对应 case。

| 参数 / 字段特征 | 常见位置 | 形态 | 建议读取 |
| --- | --- | --- | --- |
| `a_bogus` / 单个 180-192 字符长签名参数 | URL query | Base64 或自定义 Base64 变体 | `vmp/jsvmp-xhr-interceptor-env-emulation.md` |
| `X-Bogus` + `X-Gnarly` 同时出现 | URL query + request header | 双签名，一个进 URL，一个进 header | `vmp/jsvmp-dual-sign-cacheopts-firefox.md` |
| `msToken` / `verifyFp` / `fp` / 浏览器指纹 ID | Cookie 或 URL query | 长 token + 指纹 ID，常与安全 SDK 联动 | `vmp/jsvmp-xhr-interceptor-env-emulation.md` 或 `vmp/jsvmp-dual-sign-cacheopts-firefox.md` |
| `XxxYyyZzz2AaaaS` + `XxxYyyZzz2AaaaT` 同 basename Cookie 对 | Cookie | 首跳服务端下发 `S`，挑战 JS 生成同 basename 的 `T`，配合 412 challenge | `waf-cookie/rs6-cookie-412-sdenv.md` |
| `$_ts.nsd` / `$_ts.cd` / 动态 `_$xx()` 入口 | 412 challenge HTML | 内联配置 + 动态入口函数，常与 `S/T` Cookie 对同时出现 | `waf-cookie/rs6-cookie-412-sdenv.md` |
| `acw_tc` / `_abck` / `bm_sz` / `ak_bmsc` / WAF 动态 Cookie | Cookie | 服务端挑战、JS challenge 或 sensor 生成 | 先读 `waf-cookie/rs6-cookie-412-sdenv.md`，再按实际厂商补 case |
| `pr_fp` + `wasm` 同时出现 | Cookie | `pr_fp` 常为 64 位 hex；`wasm` 常为 32 位 hex，配合 `fp_bg.wasm` / `wasm_bg.wasm` | `wasm/wasm-bindgen-pr-fp-wasm-cookie-gate.md` |
| 固定长度 `sign` / `token` / `x-sign` / `x-token`，JS 只见 WASM glue | URL query / header / body | 输出随 URL、body、时间或 nonce 变化 | `wasm-protocol-recovery-playbook.md` |
| 128 / 192 / 256 字符签名，且 JS 中存在 dispatch loop | URL query / header / cookie | Base64 变体、hex、自定义字符表 | `vmp/universal-vmp-source-instrumentation.md` |

## 类型分组

| 类型 | 当前案例 | 后续可补充方向 |
| --- | --- | --- |
| VMP / JSVMP | `vmp/universal-vmp-source-instrumentation.md`、`vmp/jsvmp-xhr-interceptor-env-emulation.md`、`vmp/jsvmp-dual-sign-cacheopts-firefox.md` | 字节码反编译、不同 SDK 版本、Worker 内 VMP |
| WAF / Cookie Challenge | `waf-cookie/rs6-cookie-412-sdenv.md` | Aliyun WAF、Akamai cookie、URL suffix 变体 |
| WASM | `wasm-protocol-recovery-playbook.md`、`wasm/wasm-bindgen-pr-fp-wasm-cookie-gate.md` | Emscripten、响应解密、protobuf 包装、Worker 内 WASM |
| 协议编码 / 响应解密 | 待补充 | protobuf、AES 响应体、字体混淆、二进制 framing |
| 环境指纹 / TLS | 待补充 | Chrome/Firefox 分支、TLS/HTTP2 指纹、canvas/webgl/audio |

## 新增 Case 流程

1. 先选择目录：详细案例放入技术家族目录；跨类型模板、骨架、playbook 才放在 `cases/` 根目录。
2. 从 `_template.md` 复制为技术特征命名的新文件，例如 `wasm/wasm-aes-cbc-dynamic-key.md`。
3. 填写技术指纹、反爬类型、Phase 处理流程、核心代码模板、踩坑记录和可验证事实清单。
4. 确认内容已脱敏，只保留可复用事实。
5. 更新本 README 的“案例索引”和“指纹速查”。
6. 如果 case 暴露出新的 skill 路由规则，再同步更新 `SKILL_ROUTER.md`、`catalog.yaml` 和 active skill 副本。

## Case 完整度标准

一个合格 case 不应该只是摘要。至少包含：

| 模块 | 必填内容 |
| --- | --- |
| 技术指纹 | 可搜索关键词、资源形态、参数形态、请求特征 |
| 参数特征 | 参数名、header 名、Cookie 名、长度、字符集、出现位置、变化条件 |
| Phase 处理流程 | 从抓包、入口定位、插桩/补环境到协议验收的分阶段步骤 |
| 链路图 | `source -> entry -> builder -> writer -> sink -> verification` |
| 核心代码模板 | 脱敏后的函数骨架、hook 模板、沙箱调用方式或协议回放方式 |
| 踩坑记录 | 失败现象、错误原因、正确做法 |
| 可验证事实清单 | 下次同类目标可逐条复核的稳定事实 |

可以删掉真实域名、真实密钥和大段目标源码，但不要删掉还原路线本身。case 的目标是让后续同类目标能照着复现定位，而不是只知道“这类问题存在”。

## 审计命令

新增或移动 case 后，运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\audit-cases.ps1
```

该脚本检查详细 case 是否包含参数特征、Phase、链路图、核心代码、验证方法和可验证事实清单，并检查 README 中的 case 链接是否断链。

## 命名建议

用技术特征命名，不用具体站点命名：

```text
wasm/wasm-aes-cbc-dynamic-key.md
wasm/wasm-memory-export-sign.md
vmp/jsvmp-xhr-interceptor-env-emulation.md
waf-cookie/rs6-cookie-412-sdenv.md
response-decode/protobuf-response-aes-decode.md
```
