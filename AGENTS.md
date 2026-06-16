# reverse-lab Agent Notes

This project is a reverse-engineering workspace for Web/JS protocol recovery.

## Entry Point

- Read `SKILL_ROUTER.md` before choosing a reverse-engineering skill.
- Use the narrowest matching skill; do not jump to env rebuild, AST, iv8, or browser automation before the router gate is satisfied.
- Project-level active skills live in `.codex/skills/` and `.agents/skills/`.
- The full skill library lives in `skills-library/`.

## Artifact Policy

- Do not write downloaded target JS, HTML, WASM, fonts, cookies, packet samples, or target-specific notes into skill directories.
- Use `js_reverse_cache/` for transient investigation artifacts.
- Use `targets/<site>/` for target-specific scripts, samples, output, and notes.
- Use `cases/` for sanitized reusable verified cases.

## Browser Evidence Policy

- Camoufox MCP is the preferred browser evidence layer for Firefox/Gecko baselines, `compare_env`, `trace_property_access`, runtime hooks, source instrumentation, cookie/storage/network evidence, and browser-vs-local validation.
- CloakBrowser MCP is the optional Chrome/Chromium baseline layer. Verify availability before relying on it.
- Keep Camoufox and CloakBrowser environment samples separate. Do not mix Firefox-only and Chrome-only fingerprint facts when writing environment patches.
- Browser automation is a documented fallback, not the default final deliverable.

## Target Layout

Every reverse target must live under `targets/<source-name>/`:

```text
targets/<source-name>/
├── source/
├── scripts/
├── samples/
├── output/
└── notes.md
```

- `source/`: original JS, HTML, WASM, fonts, page source, and other raw inputs.
- `scripts/`: analysis helpers, deobfuscation scripts, environment patches, replay experiments.
- `samples/`: request/response samples, cookies, headers, fixed inputs, expected outputs, and structured evidence.
- `output/`: final runnable program or stable reproduction code.
- `notes.md`: required Chinese-readable analysis record.

For dynamic fields, keep the chain explicit: `source -> entry -> builder -> writer -> sink`. If normal and risk samples diverge, record them as separate evidence paths.

## Maintenance

- Do not add `CLAUDE.md` or `.claude/skills` back to the project.
- When changing skill names, routes, or groups, update `SKILL_ROUTER.md`, `catalog.yaml`, tool scripts, evals, and active skill copies together.
