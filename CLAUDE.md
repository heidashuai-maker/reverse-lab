# reverse-lab Claude Code Notes

This project contains project-level Claude Code skills in `.claude/skills/`.

Use `skills-library/` as the source library. Keep narrow iv8 case skills disabled until the current target explicitly matches the site or protocol.

Generated reverse-engineering artifacts should go to `js_reverse_cache/`, `targets/<site>/`, or `cases/`, never into skill source folders.

## Browser Tool Policy

Camoufox MCP is the preferred browser tool layer for Firefox/Gecko fingerprint baselines, runtime hooks, pre-injection, cookie provenance, and browser-vs-local validation. CloakBrowser MCP is the Chrome/Chromium fingerprint baseline and optional browser-automation fallback layer; verify it is available before depending on it.

Keep Camoufox and CloakBrowser environment samples separate. Browser automation is allowed only as a documented fallback after pure protocol, Node/vm/jsdom, WASM helper, and TLS/HTTP fingerprint paths have been ruled out.

## Target Directory Rule

Each reverse-engineering source must use one folder under `targets/`:

```text
targets/<source-name>/
├── source/
├── scripts/
├── samples/
├── output/
└── notes.md
```

`notes.md` is mandatory and should be written in clear Chinese by default. It should explain the source, vendor/protection family, reverse approach, key dynamic values, calculation or analysis path, difficulties, verification result, conclusion, and remaining risks. Do not paste large code blocks into notes; store code in `scripts/` or `output/` and reference the file path.

When a target needs multi-round reverse engineering, also maintain structured evidence:

- `samples/task.json`: task metadata and current stage.
- `samples/network.jsonl`: key request/response evidence.
- `samples/scripts.jsonl`: key script, entry-location, request-chain, and bridge-contract evidence.
- `samples/runtime-evidence.jsonl`: hook/intermediate/first-divergence/environment evidence.
- `samples/browser-env-camoufox.json`, `browser-env-cloakbrowser.json`, `local-env-baseline.json`, `env-diff.json`: optional browser/local environment baseline and diff evidence.
- `samples/timeline.jsonl`: progress, invalidated assumptions, and stage handoff record.
- `scripts/env/`: Node local rebuild files.
- `scripts/replay/actions.json`: optional page trigger actions.
- `output/fixtures.json` and pure/ported implementations after verification.

For dynamic fields, keep `source -> entry -> builder -> writer -> sink` explicit. Separate normal-state and risk-state evidence paths when they diverge.
