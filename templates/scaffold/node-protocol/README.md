# Node.js 纯协议骨架

用于 JS 签名逻辑可以直接提取或保持在 Node.js 中运行的场景。不要在这里硬塞 `window`、`document`，有浏览器对象依赖时改用 `vm-sandbox`。

## 验证

```powershell
node output/main.js --self-test
node output/main.js --once --url "https://example.com/api"
```
