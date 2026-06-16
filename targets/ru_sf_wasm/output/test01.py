import json
import subprocess
import sys
import time
from pathlib import Path

import requests


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGET_DIR = Path(__file__).resolve().parents[1]
NODE_HELPER = TARGET_DIR / "scripts" / "generate_cookies.js"
BROWSER_COOKIE_FILE = TARGET_DIR / "samples" / "browser_generated_cookies_latest.json"
CAPTURE_SCRIPT = TARGET_DIR / "scripts" / "capture_browser_cookies.py"
RESPONSE_FILE = TARGET_DIR / "samples" / "test01_latest_response.html"
CARD_URL = "https://kad.arbitr.ru/Card/566bf0a7-8ccc-4aef-9b45-a46be35197bf"
PROXY = "socks5h://10.86.10.212:8204"
COOKIE_MAX_AGE_SECONDS = 420
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def generate_node_cookies():
    completed = subprocess.run(
        ["node", str(NODE_HELPER), "--pretty"],
        cwd=str(TARGET_DIR),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    data = json.loads(completed.stdout)
    return {
        "wasm": data["wasm"],
        "pr_fp": data["pr_fp"],
    }


def ensure_browser_cookie_file():
    if BROWSER_COOKIE_FILE.exists() and time.time() - BROWSER_COOKIE_FILE.stat().st_mtime < COOKIE_MAX_AGE_SECONDS:
        return
    subprocess.run(
        [
            sys.executable,
            str(CAPTURE_SCRIPT),
            "--headless",
            "--proxy",
            PROXY,
            "--output",
            str(BROWSER_COOKIE_FILE),
        ],
        cwd=str(TARGET_DIR),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def load_browser_cookies():
    ensure_browser_cookie_file()
    data = json.loads(BROWSER_COOKIE_FILE.read_text(encoding="utf-8"))
    cookies = data["cookies"]
    return {
        "wasm": cookies["wasm"],
        "pr_fp": cookies["pr_fp"],
    }


def classify_response(response):
    text = response.text or ""
    if response.status_code == 451 or "/static/img/blocked.png" in text or "Доступ заблокирован" in text:
        return "blocked_451"
    if "b-case-header" in text or "js-case-header-case_num" in text:
        return "case_card_html"
    if "b-pravocaptcha-title" in text or ("pravocaptcha" in text and "RecaptchaToken" in text):
        return "pravocaptcha_gate"
    if "DDoS-Guard" in text or "/.well-known/ddos-guard/js-challenge/" in text:
        return "ddos_guard_challenge"
    return "unknown"


def extract_title(text):
    if "<title>" not in text or "</title>" not in text:
        return ""
    return text.split("<title>", 1)[1].split("</title>", 1)[0].strip()


def request_card(cookies):
    headers = {
        "user-agent": DEFAULT_UA,
        "accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
            "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "content-type": "application/x-www-form-urlencoded",
        "referer": CARD_URL,
    }
    session = requests.session()
    session.cookies.update(cookies)
    proxies = {
        "http": PROXY,
        "https": PROXY,
    }
    return session.get(CARD_URL, headers=headers, proxies=proxies, timeout=45)


def main():
    attempts = []
    final_source = "node"
    final_cookies = None
    response = None

    try:
        node_cookies = generate_node_cookies()
        response = request_card(node_cookies)
        node_classification = classify_response(response)
        attempts.append({
            "source": "node",
            "status_code": response.status_code,
            "classification": node_classification,
            "cookies": node_cookies,
        })
        final_cookies = node_cookies
    except Exception as exc:
        attempts.append({
            "source": "node",
            "error": str(exc),
        })
        node_classification = "error"

    if node_classification != "case_card_html":
        final_source = "browser_fallback"
        final_cookies = load_browser_cookies()
        response = request_card(final_cookies)
        attempts.append({
            "source": final_source,
            "status_code": response.status_code,
            "classification": classify_response(response),
            "cookies": final_cookies,
        })

    RESPONSE_FILE.write_text(response.text, encoding="utf-8", errors="replace")

    print("source:", final_source)
    print("status_code:", response.status_code)
    print("classification:", classify_response(response))
    print("title:", extract_title(response.text))
    print("cookies:", json.dumps(final_cookies, ensure_ascii=False))
    print("attempts:", json.dumps(attempts, ensure_ascii=False))
    print("response_saved_to:", RESPONSE_FILE)


if __name__ == "__main__":
    main()
