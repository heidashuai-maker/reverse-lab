# iv8 Runtime Rules

## 项目位置

任务材料写入 `targets/<site>/`：

```text
targets/<site>/
├── source/
├── scripts/
│   └── iv8/
├── samples/
├── output/
└── notes.md
```

临时下载和一次性 runtime 可写入 `js_reverse_cache/<site-or-run>/`。

## 主脚本规则

1. Python 主脚本应从当前工作目录定位 target，不使用用户机器上的绝对路径。
2. 动态 JS、HTML、cookie、headers 和请求样本不写入 skill 目录。
3. 固定输入和期望输出写入 `output/fixtures.json` 或 `samples/verification.jsonl`。
4. 把 iv8 初始化、Python HTTP session、业务请求封装在同一个主流程中，避免手工复制 cookie。

## 桥接规则

1. JS 需要网络、时间、随机数、storage、cookie 时，优先用固定样本和 Python bridge 精确提供。
2. 不要补完整浏览器环境；只补目标 runtime 实际读取的接口。
3. 需要真实浏览器值时，先按 `skills-library/shared/camoufox-evidence-flow.md` 采集。
4. 对会话绑定字段，保持同一个 Python session、同一批 cookie、同一组 headers 和同一轮 runtime 输出。

## 验证规则

1. 先 browser-vs-iv8 固定输入对比。
2. 再 iv8 输出驱动 Python HTTP 回放。
3. 最后重复至少两次，确认不是一次性 cookie 或时间窗口碰巧成功。
