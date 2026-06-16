# Tool Playbook

Use this file as the fast map from reverse-engineering task to tool choice. The default browser/runtime evidence layer is Camoufox MCP; use CloakBrowser only when a Chrome/Chromium fingerprint branch is explicitly relevant.

## Preferred Order

1. Capture one clean baseline request.
2. Find the real request.
3. Trace the initiator.
4. Diff the moving fields.
5. Add the narrowest runtime proof that still preserves the sample.
6. Reproduce one stable request.
7. Scale collection only after the first request is repeatable.

Prefer clean baselines, initiator stacks, and narrow proofs over broad hooks. Prefer focused source reads over loading giant bundles into context.

## Camoufox Recon And Network Capture

- `launch_browser`: start a fresh controlled browser profile when state isolation matters.
- `navigate`: open the target and, when needed, pre-inject `xhr`, `fetch`, `cookie`, or runtime probes before page scripts run.
- `network_capture`: start/stop/export clean request evidence.
- `list_network_requests`: enumerate document, script, XHR, fetch, preflight, and challenge traffic.
- `get_network_request`: inspect one request/response pair with headers, payload previews, and status.
- `get_request_initiator`: jump from a request back to the caller stack or script location.
- `cookies` / `get_storage` / `export_state`: preserve session state and prove replay inputs.
- `take_snapshot` / `take_screenshot` / `wait_for`: record UI gates, captcha panels, lazy regions, or workflow state.

Cookie provenance is a combined-evidence task: compare `Set-Cookie` headers from `get_network_request`, JS writes captured by `inject_hook_preset("cookie")`, and the final cookie jar from `cookies`.

## Runtime And Source Analysis

- `scripts(action="list")`: enumerate loaded scripts and candidate bundles.
- `scripts(action="get"|"save")`: inspect or preserve the exact bundle when a slice is too large for context.
- `search_code`: search loaded sources for request paths, signer names, crypto helpers, or environment probes.
- `evaluate_js`: inspect `document.cookie`, storage values, page globals, webpack caches, SDK objects, or bootstrap helpers.
- `inject_hook_preset`: add standard `xhr`, `fetch`, `cookie`, or runtime probes.
- `hook_function`: trace stable named helpers when you can do so without changing target behavior.
- `trace_property_access`: prove environment reads such as `navigator.webdriver`, `screen`, `document`, `canvas`, or `performance`.
- `hook_jsvmp_interpreter`: observe JSVMP dispatch with a low-intrusion mode first.
- `instrumentation`: use deeper source/instruction instrumentation only after lighter proof is insufficient.
- `verify_signer_offline`: compare browser-derived signer behavior against a local candidate when fixtures are stable.

Fallback recipes when a helper is missing:

- No direct source slice helper: use `search_code`, then `scripts(action="get"|"save")`.
- No automatic crypto detector: search helper names, compare fixed inputs, and route to `references/crypto-patterns.md`.
- No automatic deobfuscator: save the bundle and route to `ast-deobfuscate` or `references/obfuscation-guide.md`.

Keyword packs:

- request path: `"/api/"`, `"graphql"`, `"fetch("`, `"axios"`, `"XMLHttpRequest"`.
- signer: `"sign"`, `"token"`, `"nonce"`, `"timestamp"`, `"trace"`, `"x-sign"`, `"beforeSend"`, `"ajaxSetup"`, `"requestId"`.
- crypto: `"md5"`, `"sha"`, `"hmac"`, `"aes"`, `"rsa"`, `"crypto.subtle"`.
- environment: `"navigator"`, `"canvas"`, `"webgl"`, `"performance"`, `"webdriver"`.

## Baseline-First Proof Flow

1. Capture one clean request and response pair.
2. Use `get_request_initiator` to jump from the request to the caller stack.
3. Use `search_code` and `scripts(action="get"|"save")` to inspect the smallest relevant source region.
4. Use `hook_function` only when a named helper is stable enough to trace without poisoning the target.
5. Use `inject_hook_preset` or `navigate(pre_inject_hooks=[...])` only for narrow boundary hooks that you can justify.
6. If the target is verifier-gated or behavior-sensitive, remove invasive instrumentation and recapture a clean baseline the moment behavior changes.

## Session And Environment Handling

- `check_environment`: detect obvious automation/fingerprint gaps before investing in protocol work.
- `compare_env`: compare browser and local probes before writing environment patches.
- `evaluate_js`: run the same probe in browser context that you will later run locally.
- `cookies`, `get_storage`, `export_state`: keep replay state explicit and reproducible.
- `reset_browser_state`: start over when stale cookies or storage can poison conclusions.

Write durable evidence into `targets/<site>/samples/` or `js_reverse_cache/`, never into skill directories.

## Failure Routing

- `403`, `412`, `429`: compare headers, cookies, sign freshness, browser/session state, and request pacing.
- Business error with normal `200`: compare payload assembly order and timestamp precision.
- Decrypt failure after a successful `200`: verify whether the runtime key/iv is transformed through a helper before AES or stream decoding.
- Empty data: verify pagination, filters, referer, login state, and cursor evolution.
- Occasional success: inspect one-time tokens, session refresh, or concurrent request coupling.
- First request works but immediate replay fails: compare cookie mutation, in-memory timestamp slots, and whether a page refresh function must run before every request.
- Response gibberish: search for decrypt path, compression, protobuf, msgpack, or custom transport wrappers.
- Hooked page fails but clean page works: suspect observer effect, remove invasive hooks, and recapture the baseline before deeper tracing.

## Local Helper Scripts

Use the bundled local scripts when they are faster than re-deriving the same mechanics:

- `scripts/check_reverse_env.py`: confirm the local reverse stack quickly.
- `scripts/crypto_fingerprint.py`: classify suspicious digest or alphabet outputs.
- `scripts/protocol_diff.py`: compare captured requests or responses and surface the meaningful deltas.
- `scripts/scaffold_reverse_project.py`: start a clean Python-first collector layout.
