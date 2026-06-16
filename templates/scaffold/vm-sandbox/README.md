# Node vm/jsdom/sdenv 骨架

用于本地执行目标 JS、动态 cookie/token、轻量浏览器对象依赖或 JSVMP 最小环境复现。

原始目标 JS 放 `source/`，不要直接改。这里的 `env.js` 和 `polyfills.js` 只补已有证据证明会读取并影响结果的最小环境项。

## 验证

```powershell
node scripts/env/run.js --self-test
```
