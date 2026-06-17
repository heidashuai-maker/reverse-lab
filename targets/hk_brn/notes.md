# 香港商业登记 BRN 初始化修复记录

## 结论

当前异常的直接触发点是 `HkBrnSpider.py` 在初始化 session 时主动请求 `/fe/pa/brn/submit/generateTrn/v1`。历史会话实测显示，真实浏览器在进入业务输入页前不会立刻触发该接口；当 `agsec/Surge login` 状态未建立时，接口会返回 `System Exception - Missing login token.`。

本轮修复先验证到：只做 `CCC -> 动态 btpN -> FePublicKey/get -> sessionid/obtain` 只能拿到 `clientSessionId`，不能证明 session 合规。用户反馈后已修正门禁：初始化必须继续验证 `agsec/check-session` 和 `generateTrn`，拿不到非空 `trn` 就不能返回可用 context。

2026-06-17 现场复核：通过 `https://www.gov.hk/sc/apps/irdbrnenquiry.htm` 入口可正常跳转到税局页面，本轮会话分配到 `btp1`；初始化网络出现 `ssr/cookies`、`agsec/check-session`、`FePublicKey/get`、`sessionid/obtain`、`session/save`、`isModuleSuspended`，未出现 `generateTrn/v1`。

2026-06-17 最小 requests 验证：stub 项目基类后只加载 `HkBrnSpider.py` 的 HTTP 方法，执行 `pass_ccc -> prepare_session` 成功，返回 `api_host=https://btp2.etax.ird.gov.hk` 和 `PF2_...` 前缀的 `client_session_id`，未调用 `generateTrn/v1`。

用户反馈后修正门禁：空 `trn` 的 session 不能视为可用。`HkBrnSpider.py` 已恢复为必须拿到非空 `trn` 才返回 context，`checkApplyDoc` 也拒绝空 `trn`。live 验证显示 `prepare_session` 后 `generateTrn/v1` 返回 `code=100, message=System Exception - Missing login token.`，因此当前纯 requests 初始化仍不合规，但不会再进入采集。

补充验证：按前端代码复现 `RSA-OAEP(sessionKey)`、`AES-CBC(SessionStorageData)`，写入 `UserStatic`、`ApplData`，并补 `validateBeginApp`、`surge/revoke`、`agsec/receive/server-req` 后，`agsec/check-session` 仍为 `loginStatus=false`。当前阻塞点不是普通业务 JSON 参数，而是浏览器执行态/agsec login token。

## 请求链路与执行环节

浏览器入口链路：

```text
GovHK 入口 https://www.gov.hk/sc/apps/irdbrnenquiry.htm
-> https://btp.etax.ird.gov.hk/fe/pw/brn?language=ZH_HK
-> /fe/pw/brn/init?language=ZH_HK&setInit=true
-> /fe/pw/brn/conductbrn/intro?userStatic=BRN556
```

初始化阶段真实网络链路：

```text
POST /fe/pa/ssr/cookies
POST /fe/pa/agsec/check-session/v1
GET  /fe/pa/ssr/getMenuLink
GET  /fe/pa/kmu/FePublicKey/get
POST /fe/pa/sstorage/encrypted/sessionid/obtain
POST /fe/pa/sstorage/encrypted/sessionidandkey/query
POST /fe/pa/agsec/check-session/v1
POST /fe/pa/sstorage/encrypted/session/save
POST /fe/pa/brn/isModuleSuspended/v1
GET  /fe/pa/surge/revoke/v1
POST /fe/pa/agsec/check-session/v1
GET  /fe/pa/agsec/receive/server-req
```

点击“開始使用服務”后的关键链路：

```text
POST /fe/pa/agsec/check-session/v1
POST /fe/pa/brn/checkLogin/v1
  body: {"credentials":{"errors":[],"username":{"value":"s-brn-u1"},"type":3,"isCheckOnly":true}}
  浏览器中也可能先返回: Surge login is expired
POST /fe/pa/sstorage/encrypted/session/save
  写入 SessionStorageData.ApplData
POST /fe/pa/brn/validateBeginApp/v1
  body: {"language":"ZH_HK","userStatus":"P","trn":""}
  成功返回 code=0 和 applStartDtTime
POST /fe/pa/sstorage/encrypted/session/save
  用服务端返回 applStartDtTime 覆盖 SessionStorageData.ApplData
POST /fe/pa/agsec/check-session/v1
GET  /fe/pa/agsec/receive/server-req
```

进入服务选择、业务输入、验证码后，才进入业务提交链路：

```text
选择「申請商業登記冊內資料的摘錄及有效的商業/分行登記證複本」
-> 进入 /fe/pw/brn/brsupply/enterbusinessdetails?userStatic=BRN556
-> 输入 brn/brh
-> 选择 CBRC
-> 验证码 validate_audio_angular.php
-> POST /fe/pa/brn/submit/generateTrn/v1
-> POST /fe/pa/brn/checkApplyDoc/v1
```

## loginStatus 验证点

判断会话是否合规不能只看 `clientSessionId`。核心验证接口是：

```text
POST /fe/pa/agsec/check-session/v1
```

正确状态应至少满足：

```json
{
  "loginStatus": {"value": true},
  "surgeId": {"value": "s-brn-u1"},
  "valid": {"value": true}
}
```

如果该接口仍返回：

```json
{
  "loginStatus": {"value": false},
  "surgeId": {"value": ""}
}
```

则当前 session 没有建立 login token，后续请求会失败：

```text
generateTrn/v1 -> System Exception - Missing login token.
checkApplyDoc/v1 -> System Exception - Missing login token.
```

当前纯 requests 已补过以下内容但仍无法让 `loginStatus` 变成 true：

- 跟随 `ntp-ccc-prd=PF1/PF2` 动态选择 `btp1/btp2`。
- 持续携带 `ntp-client-id` 和 `screenid`。
- `RSA-OAEP` 加密 AES hex key 后请求 `sessionid/obtain`。
- 使用 `AES-CBC` 写入 `SessionStorageData`，包含 `UserStatic=P` 和 `ApplData.applStartDtTime`。
- 请求 `checkLogin`、`validateBeginApp`、`surge/revoke`、`agsec/receive/server-req`。

因此当前缺口是：浏览器执行态/agsec 如何把会话状态从 `loginStatus=false` 推进到 `loginStatus=true`。这一步需要继续逆 `agsec`，或改为浏览器初始化合规会话后再复用。

## 已改动

- `ntp-ccc-prd=PF1/PF2...` 解析为后续 API 主机 `btp1/btp2`。
- CCC 生成的 `clientId` 写入后续请求头 `ntp-client-id`。
- 补充真实链路中出现的 `screenid: SC-556-0001`。
- `build_ready_session()` 必须通过 `generateTrn/v1` 拿到非空 `trn` 才返回 context。
- `checkApplyDoc` 增加空 `trn` 拒绝，避免不合规 session 继续采集。
- 验证码、`checkApplyDoc` 的 URL、`Origin` 和 `Referer` 跟随动态 `api_host`。

## 仍需关注

下一步要么继续逆 `agsec/check-session` 如何在浏览器中变为 `loginStatus=true`，要么改为“浏览器初始化会话 + 浏览器上下文提交/requests 复用”的混合链路。

## 2026-06-17 追加结论：loginStatus=true 的缺失环节

本轮已确认不需要先采用浏览器初始化 session 兜底。`loginStatus=true` 的关键缺失环节是点击“开始使用服务”后，前端在 `checkLogin/v1` 返回 `Surge login is expired` 时会继续请求：

```text
POST /fe/pa/surge/acquire/v1
body: {"surgeId":"s-brn-u1"}
screenid: SC-556-0201
```

该接口成功返回：

```json
{"code":"0","message":"success","acquire":true}
```

同时响应头写入 HttpOnly cookie：

```text
ntp-etax-prd=<JWT>; domain=.etax.ird.gov.hk; secure; HttpOnly
```

后续 `POST /fe/pa/agsec/check-session/v1` 才会从：

```json
{"loginStatus":{"value":false},"surgeId":{"value":""},"valid":{"value":true}}
```

变为：

```json
{"loginStatus":{"value":true},"surgeId":{"value":"s-brn-u1"},"valid":{"value":true}}
```

因此 `generateTrn/v1` 报 `System Exception - Missing login token.` 的直接原因不是业务参数，也不是 `trn` 生成逻辑，而是初始化阶段没有调用 `surge/acquire/v1`，没有拿到 `ntp-etax-prd` 登录 token cookie。

补充链路也已确认：

```text
GET  /fe/pw/brn/init?language=ZH_HK&setInit=true
POST /fe/pa/ccc/ccc-service/check-browser-request/v2
POST /fe/pa/ssr/cookies
  body: {"cookie":{"name":"language","value":"ZH_HK"}}
POST /fe/pa/agsec/check-session/v1
GET  /fe/pa/kmu/FePublicKey/get
GET  /fe/pa/agsec/receive/server-req
POST /fe/pa/sstorage/encrypted/sessionid/obtain
POST /fe/pa/brn/checkLogin/v1
  body: {"credentials":{"errors":[],"username":{"value":"s-brn-u1"},"type":3,"isCheckOnly":true}}
POST /fe/pa/surge/acquire/v1
  body: {"surgeId":"s-brn-u1"}
POST /fe/pa/brn/validateBeginApp/v1
  body: {"language":"ZH_HK","userStatus":"P","trn":""}
POST /fe/pa/agsec/check-session/v1
POST /fe/pa/brn/submit/generateTrn/v1
```

CCC 判断：当前证据不支持“CCC 验证不通过”这个判断。原因是纯请求已经能稳定拿到 `ntp-ccc-prd`、`X-ntp-version`，`agsec/check-session` 在失败时仍返回 `valid=true`，并且补上 `surge/acquire/v1` 后同一纯请求 session 可得到 `loginStatus=true` 和非空 `trn`。CCC 是前置必要条件，但本次 missing login token 的分叉点是 `surge/acquire/v1`。

代码落地：`D:\code\spider2\spiders\HkBrnSpider.py` 已补：

- `ssr/cookies` 写入 `language=ZH_HK`。
- 初始化阶段补 `agsec/receive/server-req`。
- 新增 `checkLogin -> surge/acquire -> validateBeginApp -> check-session`。
- `build_ready_session()` 必须先确认 `loginStatus=true`、`surgeId=s-brn-u1`，再调用 `generateTrn/v1`。

验证记录：使用 spider 本体方法、stub 项目基类并跳过验证码步骤，只验证初始化到 `trn`：

```text
api_host https://btp1.etax.ird.gov.hk
loginStatus True
surgeId s-brn-u1
trn 5562606174297486
has_ntp_etax True
```
