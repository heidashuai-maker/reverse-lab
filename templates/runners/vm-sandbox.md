# Node vm/jsdom/sdenv 沙箱模板

适用于服务端下发 JS、动态 cookie/token、JSVMP 可在本地运行的目标。

推荐结构：

```text
scripts/env/
├── entry.js
├── env.js
├── polyfills.js
├── patch-plan.md
├── run.js
└── capture.json
```

最小要求：

1. 原始 JS 放 `source/`，不要直接修改。
2. `env.js` 只补 first divergence 对应的最小对象。
3. 每轮补丁更新 `patch-plan.md`，记录浏览器证据、本地差异、补丁原因和复测结果。
4. `success: true` 只代表脚本能加载，不代表签名可用。
5. 若脚本能生成值但服务端不接受，进入 `env-patch/references/sandbox-fingerprint-validation.md`。
