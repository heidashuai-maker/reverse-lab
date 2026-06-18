# 案例：<技术特征名称>

> 难度：★☆☆☆☆ ~ ★★★★★
> 反爬类型：签名型 / 行为型 / 纯混淆 / 混合型
> 首选路线：find-crypto-entry / ast-deobfuscate / env-patch / web-protocol-recovery / browser-hook-snippets / 其他
> 复现形态：纯 Python / 纯 Node.js / Node vm-jsdom-sdenv / Python+WASM helper / 浏览器自动化兜底
> 推荐目录：cases/<技术家族或问题类型>/
> 最后验证日期：YYYY-MM-DD

## 适用范围

说明这个案例解决哪一类问题，以及不适用哪一类问题。

- 适用：
- 不适用：

## 存放位置与命名

- 详细案例放入技术家族目录，例如 `cases/vmp/`、`cases/wasm/`、`cases/waf-cookie/`。
- 跨类型模板、骨架或 playbook 才放在 `cases/` 根目录。
- 文件名使用小写英文和短横线：`<family>-<mechanism>-<entry-or-sink>-<recovery-method>.md`。
- 不使用具体站点、域名、客户名、真实参数值或 Cookie 值命名。

## 技术指纹

### JS / WASM / 资源特征

- [ ] 可搜索关键词或正则：
- [ ] 关键脚本、WASM、Worker、SDK 或 glue 文件形态：
- [ ] 文件大小、加载顺序、导出函数或入口特征：
- [ ] 资源版本证据：SHA256、ETag、Last-Modified、查询串版本或构建号：

### 参数与请求特征

- [ ] 参数名、header、cookie 或 body 字段：
- [ ] 长度、字符集、编码格式：
- [ ] 预热请求、挑战请求、业务请求链路：

## 参数特征（快速路由）

> 这里写给后续检索用。发现同名参数、同长度、同位置时，应能直接命中本 case。

| 参数 / 字段 | 位置 | 长度 / 字符集 | 生成时机 | 判定价值 |
| --- | --- | --- | --- | --- |
| | URL query / header / Cookie / body | | 请求前 / challenge 后 / SDK 初始化后 | 高 / 中 / 低 |

```text
命中规则：
- 参数名完全一致：
- 长度或字符集一致：
- 与哪些脚本/SDK/资源特征同时出现时可高置信度命中：
```

### 运行时与环境特征

- [ ] 是否读取 navigator / screen / canvas / WebGL / storage / cookie：
- [ ] 是否依赖时间、随机数、会话、TLS/HTTP 指纹：
- [ ] 是否使用 Worker、WASM memory、SharedArrayBuffer、WebCrypto：

## 指纹检测规则

```text
快速检测：
1. 搜索关键词：
2. 查看网络请求：
3. 查看脚本/WASM 导出：
4. 触发一次业务请求并记录动态字段：

匹配判定：
- 高置信度：
- 中置信度：
- 排除条件：
```

## 反爬类型判定

```text
判定结果：
判定依据：
首选 skill：
为什么不是其他路线：
```

## 已验证定位路径

按最短可复现路径写，不写大段源码。

```text
步骤 1：
步骤 2：
步骤 3：
步骤 4：
```

## Phase 处理流程

### Phase 1：指纹与请求确认

```text
目标：
输入：
操作：
产物：
成功判定：
```

### Phase 2：入口定位

```text
目标：
输入：
操作：
产物：
成功判定：
```

### Phase 3：重建 / 插桩 / 补环境

```text
目标：
输入：
操作：
产物：
成功判定：
```

### Phase 4：协议回放验收

```text
目标：
输入：
操作：
产物：
成功判定：
```

## 链路图

用 `source -> entry -> builder -> writer -> sink` 明确动态字段来源。

```text
source:
entry:
builder:
writer:
sink:
verification:
```

## 加密 / 编码 / 签名方案

- 算法：
- 密钥来源：
- 输入字段：
- 输出字段：
- 编码方式：
- 会话绑定：
- 环境绑定：

## 还原代码模板

只放脱敏骨架，不放真实密钥、真实 URL、完整目标源码。

```javascript
// Node.js skeleton
```

```python
# Python skeleton
```

## 验证方法

- 本地函数级验证：
- browser-vs-local 验证：
- 协议回放验证：
- 资源版本验证：
- 响应分类标准：
- 失败判定：

## 踩坑记录

| # | 坑 | 现象 | 正确做法 |
| --- | --- | --- | --- |
| 1 | | | |

## 变体说明

| 变体 | 差异点 | 调整策略 |
| --- | --- | --- |
| A | | |

## 可验证事实清单

下次同类站点或同站升级时逐条核对。

- [ ] 事实 1：
- [ ] 事实 2：
- [ ] 事实 3：
- [ ] 事实 4：
- [ ] 事实 5：

## 脱敏检查

- [ ] 未包含真实 Cookie、token、账号、密钥。
- [ ] 未包含完整目标 URL 或敏感域名。
- [ ] 未粘贴大段目标 JS / WASM / HTML。
- [ ] 原始材料已放在 `targets/<site>/` 或 `js_reverse_cache/`。
