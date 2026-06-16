# Python 纯协议骨架

用于已经确认可以脱离浏览器的协议回放。这里不保存真实 cookie、headers 或目标样本；固定输入和浏览器输出应放到 `fixtures.json`。

## 文件

- `main.py`：命令入口，先跑 fixture，再按需发起一次请求。
- `signer.py`：签名、加密或 token 计算。
- `client.py`：HTTP 请求封装。
- `fixtures.json`：固定输入、浏览器输出和本地输出。
- `config/headers.example.json`：请求头示例，不放真实敏感值。

## 验证

```powershell
python output/main.py --self-test
python output/main.py --once --url "https://example.com/api"
```
