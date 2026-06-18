import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import requests
except ImportError as exc:
    raise SystemExit("requests is required. Install it with: pip install requests") from exc

try:
    import urllib3
except ImportError:
    urllib3 = None


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


BASE_URL = "https://kad.arbitr.ru"
TARGET_DIR = Path(__file__).resolve().parents[1]
NODE_HELPER = TARGET_DIR / "scripts" / "generate_cookies.js"
DEFAULT_CARD_ID = "566bf0a7-8ccc-4aef-9b45-a46be35197bf"
DEFAULT_PROXY = "http://127.0.0.1:7890"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_RESPONSE_PATH = TARGET_DIR / "samples" / "kad_request_card_response.html"


def normalize_proxy(proxy):
    if proxy is None or proxy == "":
        return None
    return {"http": proxy, "https": proxy}


def generate_cookies(user_agent=DEFAULT_UA):
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node executable was not found in PATH")

    completed = subprocess.run(
        [node, str(NODE_HELPER), "--ua", user_agent],
        cwd=str(TARGET_DIR),
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "cookie helper failed:\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    data = json.loads(completed.stdout)
    cookies = data.get("cookies") or {}
    if not cookies.get("pr_fp") or not cookies.get("wasm"):
        raise RuntimeError(f"cookie helper did not return pr_fp/wasm: {data}")
    return {
        "pr_fp": cookies["pr_fp"],
        "wasm": cookies["wasm"],
        "cookieHeader": f"pr_fp={cookies['pr_fp']}; wasm={cookies['wasm']}",
        "userAgent": data.get("userAgent") or user_agent,
    }


def build_card_url(card_id_or_url):
    if str(card_id_or_url).startswith("http"):
        return str(card_id_or_url)
    return f"{BASE_URL}/Card/{card_id_or_url}"


def classify_card_response(response):
    text = response.text or ""
    if response.status_code == 451 or "/static/img/blocked.png" in text:
        return "blocked_451"
    if "b-case-header" in text or "js-case-header-case_num" in text:
        return "case_card_html"
    if "b-pravocaptcha-title" in text or ("pravocaptcha" in text and "RecaptchaToken" in text):
        return "pravocaptcha_gate"
    if "DDoS-Guard" in text or "/.well-known/ddos-guard/js-challenge/" in text:
        return "ddos_guard_challenge"
    return "unknown"


def request_card(card_id_or_url, cookie_info, proxy=DEFAULT_PROXY, timeout=45, verify_tls=False):
    if not verify_tls and urllib3:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    url = build_card_url(card_id_or_url)
    headers = {
        "User-Agent": cookie_info["userAgent"],
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
            "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Referer": url,
        "Cookie": cookie_info["cookieHeader"],
    }
    return requests.get(
        url,
        headers=headers,
        proxies=normalize_proxy(proxy),
        timeout=timeout,
        verify=verify_tls,
    )


def response_summary(response, save_path=None):
    classification = classify_card_response(response)
    summary = {
        "status_code": response.status_code,
        "classification": classification,
        "url": response.url,
        "content_type": response.headers.get("content-type", ""),
        "body_length": len(response.content),
    }
    if save_path:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        summary["saved_to"] = str(path.resolve())
    return summary


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate pr_fp/wasm with the local JS helper and optionally verify a card page."
    )
    parser.add_argument("--proxy", default=DEFAULT_PROXY, help="Proxy for HTTP/HTTPS. Empty string disables proxy.")
    parser.add_argument("--ua", default=DEFAULT_UA)
    parser.add_argument("--card-id", default=DEFAULT_CARD_ID, help="Card id or full /Card URL.")
    parser.add_argument("--skip-card", action="store_true", help="Only generate cookies; do not request the card page.")
    parser.add_argument("--save-response", default=str(DEFAULT_RESPONSE_PATH), help="Path for the card HTML response.")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--verify-tls", action="store_true", help="Enable TLS certificate verification.")
    return parser


def main():
    args = build_parser().parse_args()
    cookie_info = generate_cookies(args.ua)
    output = {
        "proxy": args.proxy or None,
        "cookies": {
            "pr_fp": cookie_info["pr_fp"],
            "wasm": cookie_info["wasm"],
        },
        "cookieHeader": cookie_info["cookieHeader"],
    }

    if not args.skip_card:
        response = request_card(
            args.card_id,
            cookie_info,
            proxy=args.proxy or None,
            timeout=args.timeout,
            verify_tls=args.verify_tls,
        )
        output["cardProbe"] = response_summary(response, save_path=args.save_response)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
