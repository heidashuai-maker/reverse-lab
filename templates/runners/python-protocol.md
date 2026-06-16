# Python 纯协议模板

适用于标准算法或已完整还原的请求协议。推荐结构：

```text
output/
├── main.py
├── signer.py
├── client.py
├── fixtures.json
└── README.md
```

最小要求：

1. `signer.py` 提供固定输入自检，能复现浏览器样本。
2. `client.py` 使用 `requests` 或 `curl_cffi.requests`，优先保持 `params=`、`json=`、`cookies=` 的标准写法。
3. 如果浏览器值可用但 Python 请求失败，先检查 TLS / HTTP2 / header / cookie，不要先改 signer。
4. `fixtures.json` 保存固定输入、浏览器输出、本地输出和验收状态。

验收命令示例：

```powershell
python output/main.py --self-test
python output/main.py --once
```
