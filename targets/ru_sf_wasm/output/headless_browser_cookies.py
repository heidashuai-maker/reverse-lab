import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


TARGET_DIR = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = TARGET_DIR / "scripts" / "capture_browser_cookies.py"
DEFAULT_PROXY = "http://127.0.0.1:7890"
DEFAULT_CARD_ID = "566bf0a7-8ccc-4aef-9b45-a46be35197bf"
DEFAULT_OUTPUT = TARGET_DIR / "samples" / "browser_generated_cookies_headless_7890.json"


def capture_with_chrome(proxy, card_id, output_path, headed=False):
    command = [
        sys.executable,
        str(CAPTURE_SCRIPT),
        "--proxy",
        proxy,
        "--card-id",
        card_id,
        "--output",
        str(output_path),
    ]
    if not headed:
        command.append("--headless")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        command,
        cwd=str(TARGET_DIR),
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "headless browser cookie capture failed:\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return json.loads(completed.stdout)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Standalone headless Chrome/CDP cookie plan. Use only as a browser-auto fallback."
    )
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    parser.add_argument("--card-id", default=DEFAULT_CARD_ID)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--headed", action="store_true", help="Show Chrome instead of running headless.")
    return parser


def main():
    args = build_parser().parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    captured = capture_with_chrome(args.proxy, args.card_id, output_path, headed=args.headed)
    cookies = captured.get("cookies") or {}
    validation = captured.get("requestValidation") or {}
    summary = {
        "mode": "headless_browser_cdp" if not args.headed else "headed_browser_cdp",
        "proxy": args.proxy,
        "cookies": {
            "pr_fp": cookies.get("pr_fp"),
            "wasm": cookies.get("wasm"),
        },
        "requestValidation": validation,
        "saved_to": str(output_path.resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
