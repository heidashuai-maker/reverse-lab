# reverse-lab Agent Notes

This project is a reverse-engineering workspace for Web/JS protocol recovery.

## Skill Policy

- Project-level active skills live in `.codex/skills/`.
- The full skill library lives in `skills-library/`.
- Keep only broadly useful core skills active by default.
- Do not enable narrow site-case skills unless the current target clearly matches them.

## Artifact Policy

- Do not write downloaded target JS, HTML, WASM, fonts, cookies, or packet samples into skill directories.
- Use `js_reverse_cache/` for transient investigation artifacts.
- Use `targets/<site>/` for target-specific scripts, samples, and notes.
- Use `cases/` for reusable verified cases.

## Browser Tool Policy

- Camoufox MCP is the preferred browser tool layer for this project. Use it for Firefox/Gecko fingerprint baselines, `compare_env`, runtime hooks, pre-injection, cookie provenance, and browser-vs-local validation when available.
- CloakBrowser MCP is the Chrome/Chromium fingerprint baseline and optional browser-automation fallback layer. Treat it as a Playwright MCP-compatible bridge backed by CloakBrowser Chromium; verify availability before relying on it.
- Keep Camoufox and CloakBrowser environment samples separate. Do not mix Firefox-only and Chrome-only fingerprint facts when writing environment patches.
- Browser automation is not the default final deliverable. It is allowed only as a documented fallback after pure protocol, Node/vm/jsdom, WASM helper, and TLS/HTTP fingerprint paths have been ruled out.

## Target Layout Policy

Every source or site being reversed must live under `targets/<source-name>/`.

Use this lightweight structure:

```text
targets/<source-name>/
├── source/
├── scripts/
├── samples/
├── output/
└── notes.md
```

- `source/`: original JS, HTML, WASM, fonts, page source, and other raw analysis inputs.
- `scripts/`: analysis helpers, deobfuscation scripts, environment patches, replay experiments. Use `scripts/env/` for Node local rebuild and `scripts/replay/` for reproducible page actions.
- `samples/`: test samples, request/response samples, cookies, headers, fixed inputs, expected outputs, and structured evidence files.
- `output/`: final runnable program or stable reproduction code.
- `notes.md`: required Chinese-readable analysis record.

`notes.md` should be primarily descriptive, not a code dump. It should cover source information, reverse route, vendor/protection identification, key values, how values are calculated or located, hard parts, verification evidence, conclusion, and remaining risks. Put code in `scripts/` or `output/`, then reference those files from the notes.

Target evidence should follow this lightweight artifact contract when applicable:

- `samples/task.json`: task metadata, current stage, target request, success criteria, current summary.
- `samples/network.jsonl`: append-only key request and response evidence.
- `samples/scripts.jsonl`: append-only key script, initiator, function, entry-location, request-chain, and bridge-contract evidence.
- `samples/runtime-evidence.jsonl`: append-only hook, breakpoint, intermediate value, first-divergence, and environment-read evidence.
- `samples/browser-env-camoufox.json`, `browser-env-cloakbrowser.json`, `local-env-baseline.json`, `env-diff.json`: optional browser/local environment baselines and diff evidence.
- `samples/timeline.jsonl`: append-only progress, invalidated assumptions, and stage handoff record.
- `scripts/env/entry.js`, `env.js`, `polyfills.js`, `capture.json`: current Node local rebuild state.
- `scripts/replay/actions.json`: optional reproducible trigger actions.
- `output/fixtures.json`, `pure-*.js`, `pure_*.py`: stable fixtures and pure/ported implementations after rebuild is verified.

For dynamic fields, keep the chain explicit: `source -> entry -> builder -> writer -> sink`. If normal and risk samples diverge, record them as separate evidence paths instead of merging them into one conclusion.

## Default Workflow

1. Identify whether the task is entry location, browser hook, AST deobfuscation, Node environment patching, iv8 replay, WAF cookie reproduction, captcha protocol, or full protocol recovery.
2. Use the narrowest matching active skill.
3. If a library-only skill is needed, enable it explicitly or read it from `skills-library/`.
4. Keep generated project artifacts outside the skill source folders.
