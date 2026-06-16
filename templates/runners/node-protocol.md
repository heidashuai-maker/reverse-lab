# Node.js 纯协议模板

适用于 JS 算法可提取，但迁移 Python 风险较高的目标。

推荐结构：

```text
output/
├── main.js
├── signer.js
├── client.js
├── fixtures.json
└── package.json
```

最小要求：

1. `signer.js` 只做签名 / 加密 / token 计算，不混入请求翻页逻辑。
2. `main.js` 先跑 fixture，再发真实请求。
3. 如果后续由 Python 调用 Node helper，优先使用本地 HTTP 中间层或稳定 CLI，不要在 Python 中拼接大段 JS。
4. 如果依赖浏览器对象，转 `vm-sandbox.md` 或 `env-patch`，不要把 `window/document` 硬塞进纯协议模板。
