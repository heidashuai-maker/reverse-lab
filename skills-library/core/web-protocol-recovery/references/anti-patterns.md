# Anti-Patterns

- Do not ask the user to manually inspect giant bundles if tooling can inspect them.
- Do not skip `chrome-devtools` or `js-reverse` on a fresh target unless you report a real blocker.
- Do not jump straight to Selenium or Playwright when a direct API exists.
- Do not install broad hooks before capturing a clean baseline on verifier-gated or behavior-sensitive targets.
- Do not confuse business-layer params with wire-layer params.
- Do not trust helper names without fixed-input proof.
- Do not call browser-only behavior before checking page-specific headers or cookies.
- Do not hardcode rotating cookies before proving who writes them and how they refresh.
- Do not bury every concern in one `main.py`.
- Do not stop after one lucky success.
- Do not ship a browser automation script when the task is protocol-recoverable.
- Do not hide automation behind words like "temporary collector" or "reliable fallback".
- Do not leave final JS helpers coupled to `window`, `document`, browser storage, or manual browser state when they can be made local and deterministic.
