---
name: iv8-web-reverse
description: >-
  通用 Python + iv8 + requests Web/JS 复现 adapter。仅当用户明确要求用 iv8 执行浏览器侧 JS、防护页 JS、动态 cookie、签名 SDK 或请求拦截器，并用同一个 Python 主脚本发真实 HTTP 请求时使用；如果目标命中 Boss、京东 h5st、拼多多 anti_content、抖音 BDMS、小红书或瑞数等更窄 adapter，优先转对应 adapter。不要用于普通入口定位、DevTools hook 脚本、Node.js/vm/jsdom 补环境、整文件 AST 解混淆或端到端纯协议恢复。
---

# iv8-web-reverse

本 skill 是通用 iv8 运行时复现入口。它只在“交付形态已经明确是 Python + iv8 + requests”时使用。

## 边界

使用本 skill：

1. 用户明确要紧凑 Python 主脚本。
2. 需要 iv8 执行浏览器 JS、challenge runtime、SDK 初始化或请求拦截器。
3. 后续 HTTP 请求由 Python `requests` / `httpx` / `curl_cffi` 发起。
4. 没有更窄的站点 adapter 可用。

不要使用本 skill：

1. 入口未知，只是想找 sign/token/cookie 来源。转 `find-crypto-entry`。
2. 只要浏览器 hook 片段。转 `browser-hook-snippets`。
3. 入口已知但目标是 Node.js/vm/jsdom/sdenv 补环境。转 `env-patch`。
4. 目标是纯协议 Python 采集器。转 `web-protocol-recovery`。
5. 目标是具体已覆盖站点。转 `adapters/*-iv8`。

## 必读参考

- `references/iv8-runtime-rules.md`：iv8 脚本结构、缓存和桥接规则。
- `references/camoufox-bridge.md`：用 Camoufox 采集真实浏览器输入、环境和请求样本。

## 工作流

1. 确认更窄 adapter 是否命中。
2. 在 `targets/<site>/` 下维护材料，不写入 skill 目录。
3. 用 Camoufox 采集固定输入、cookie/storage、关键请求和环境基准。
4. 明确 JS 入口、初始化顺序、需要暴露给 JS 的 Python bridge。
5. 用 iv8 跑最小 JS runtime，先验证固定输入输出。
6. 用同一个 Python session 发真实请求，保持 cookie、headers、TLS/HTTP 指纹和业务参数一致。
7. 将固定输入、浏览器输出、本地输出和回放结果写入 `samples/verification.jsonl` 或 `output/fixtures.json`。

## 输出要求

交付时说明：

1. 使用的 JS 材料来源和缓存路径。
2. iv8 初始化顺序。
3. Python 与 JS 的桥接接口。
4. cookie/header/url suffix/sign 参数的来源。
5. 至少一组固定输入的 browser-vs-iv8 输出对比。
6. HTTP 回放结果和剩余风险。
