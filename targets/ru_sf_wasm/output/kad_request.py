import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from curl_cffi import requests
except ImportError as exc:
    raise SystemExit(
        "curl_cffi is required. Install it with: pip install curl_cffi"
    ) from exc

BASE_URL = "https://kad.arbitr.ru"
TARGET_DIR = Path(__file__).resolve().parents[1]
HELPER_PATH = TARGET_DIR / "scripts" / "generate_cookies.js"
CAPTURE_BROWSER_COOKIES_PATH = TARGET_DIR / "scripts" / "capture_browser_cookies.py"
DDG_MARK_BODY_PATH = TARGET_DIR / "samples" / "browser_ddg_req_08_mark_body.txt"
DEFAULT_CARD_ID = "566bf0a7-8ccc-4aef-9b45-a46be35197bf"
DEFAULT_PROXY = "socks5h://10.86.10.212:8204"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def chrome_major(user_agent):
    match = re.search(r"(?:Chrome|Chromium)/(\d+)", user_agent)
    return match.group(1) if match else "120"


def sec_ch_ua(user_agent):
    major = chrome_major(user_agent)
    return f'"Google Chrome";v="{major}", "Chromium";v="{major}", "Not)A;Brand";v="24"'


def compact_json(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def response_payload(response, preview=500):
    content_type = response.headers.get("content-type", "")
    item = {
        "status_code": response.status_code,
        "url": str(response.url),
        "content_type": content_type,
    }
    set_cookie = response.headers.get("set-cookie")
    if set_cookie:
        item["set_cookie"] = set_cookie

    if "application/json" in content_type:
        try:
            item["json"] = response.json()
            return item
        except ValueError:
            pass

    if content_type.startswith("image/"):
        item["body_length"] = len(response.content)
        return item
    item["text_preview"] = response.text[:preview]
    return item


def classify_card_response(response):
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


class KadClient:
    def __init__(self, user_agent=DEFAULT_UA, impersonate="chrome120", proxy=DEFAULT_PROXY):
        self.user_agent = user_agent
        self.session = requests.Session(impersonate=impersonate)
        if proxy:
            self.session.proxies.update({
                "http": proxy,
                "https": proxy,
            })

    def base_headers(self):
        return {
            "User-Agent": self.user_agent,
            # "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "sec-ch-ua": f'"Google Chrome";v="120", "Chromium";v="120", "Not)A;Brand";v="24"',
            "accept-encoding": "gzip, deflate, br, zstd"
        }

    def browser_hint_headers(self):
        return {
            "sec-ch-ua": sec_ch_ua(self.user_agent),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    def ddg_headers(self, referer, accept="*/*"):
        return {
            **self.base_headers(),
            **self.browser_hint_headers(),
            "Accept": accept,
            "Referer": referer,
        }

    def bootstrap(self):
        response = self.session.get(
            f"{BASE_URL}/Version/Change",
            params={"mode": "Full", "returnUrl": "/"},
            headers={
                **self.base_headers(),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
            },
            allow_redirects=True,
            timeout=30,
        )
        return response

    def is_ddg_challenge(self, response):
        text = response.text[:2000] if response.content else ""
        return (
                response.status_code == 403
                and (
                        "DDoS-Guard" in text
                        or "/.well-known/ddos-guard/js-challenge/" in text
                )
        )

    def extract_ddg_id(self, response):
        etag = response.headers.get("etag", "").strip().strip('"')
        if etag:
            return etag

        match = re.search(r"/(?:set/)?id/([A-Za-z0-9_-]+)", response.text)
        return match.group(1) if match else None

    def load_ddg_mark_body(self, mark_body_path):
        path = Path(mark_body_path or DDG_MARK_BODY_PATH)
        body = path.read_text(encoding="utf-8").strip()
        if not body:
            raise ValueError(f"empty DDoS-Guard mark body: {path}")
        return body, path

    def replay_ddg_challenge(self, challenge_url, mark_body_path=None):
        summary = {
            "challengeUrl": challenge_url,
            "cookiesBefore": self.session.cookies.get_dict(),
            "steps": [],
        }

        def record(label, response, preview=80):
            item = response_payload(response, preview=preview)
            item["label"] = label
            summary["steps"].append(item)
            return item

        asset_specs = [
            (
                "index.css",
                f"{BASE_URL}/.well-known/ddos-guard/js-challenge/index.css",
                "text/css,*/*;q=0.1",
            ),
            (
                "view.js",
                f"{BASE_URL}/.well-known/ddos-guard/js-challenge/view.js",
                "*/*",
            ),
            (
                "index.js",
                f"{BASE_URL}/.well-known/ddos-guard/js-challenge/index.js",
                "*/*",
            ),
        ]
        for label, url, accept in asset_specs:
            record(
                label,
                self.session.get(
                    url,
                    headers=self.ddg_headers(challenge_url, accept=accept),
                    timeout=30,
                ),
            )

        check_response = self.session.get(
            "https://check.ddos-guard.net/check.js",
            headers=self.ddg_headers(f"{BASE_URL}/", accept="*/*"),
            timeout=30,
        )
        record("check.js", check_response)
        challenge_id = self.extract_ddg_id(check_response)
        summary["challengeId"] = challenge_id
        if not challenge_id:
            summary["error"] = "missing_ddg_challenge_id"
            summary["cookiesAfter"] = self.session.cookies.get_dict()
            return summary, None

        image_accept = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        record(
            "origin-id",
            self.session.get(
                f"{BASE_URL}/.well-known/ddos-guard/id/{challenge_id}",
                headers=self.ddg_headers(challenge_url, accept=image_accept),
                timeout=30,
            ),
        )
        record(
            "check-set-id",
            self.session.get(
                f"https://check.ddos-guard.net/set/id/{challenge_id}",
                headers=self.ddg_headers(f"{BASE_URL}/", accept=image_accept),
                timeout=30,
            ),
        )

        mark_body, mark_path = self.load_ddg_mark_body(mark_body_path)
        summary["markBodyPath"] = str(mark_path.resolve())
        summary["markBodyBytes"] = len(mark_body.encode("utf-8"))
        mark_headers = {
            **self.ddg_headers(challenge_url, accept="*/*"),
            "Content-Type": "text/plain;charset=UTF-8",
        }
        for index in range(2):
            record(
                f"mark-{index + 1}",
                self.session.post(
                    f"{BASE_URL}/.well-known/ddos-guard/mark/",
                    headers=mark_headers,
                    data=mark_body.encode("utf-8"),
                    timeout=30,
                ),
            )

        retry_response = self.session.get(
            challenge_url,
            headers={
                **self.base_headers(),
                **self.browser_hint_headers(),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Referer": challenge_url,
            },
            allow_redirects=True,
            timeout=30,
        )
        summary["retry"] = response_payload(retry_response, preview=120)
        summary["cookiesAfter"] = self.session.cookies.get_dict()
        return summary, retry_response

    def generate_validation_cookies(self):
        node = shutil.which("node")
        if not node:
            raise RuntimeError("node executable was not found in PATH")

        command = [node, str(HELPER_PATH), "--ua", self.user_agent]
        completed = subprocess.run(
            command,
            cwd=str(TARGET_DIR),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "cookie helper failed:\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

        return json.loads(completed.stdout)

    def generate_browser_validation_cookies(self, proxy=None, headless=True):
        command = [
            sys.executable,
            str(CAPTURE_BROWSER_COOKIES_PATH),
            "--output",
            str(TARGET_DIR / "samples" / "browser_generated_cookies_latest.json"),
        ]
        if proxy:
            command.extend(["--proxy", proxy])
        if headless:
            command.append("--headless")

        completed = subprocess.run(
            command,
            cwd=str(TARGET_DIR),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "browser cookie capture failed:\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

        captured = json.loads(completed.stdout)
        cookies = captured.get("cookies") or {}
        if not cookies.get("pr_fp") or not cookies.get("wasm"):
            raise RuntimeError(f"browser capture did not return pr_fp/wasm: {captured}")
        return {
            "pr_fp": cookies["pr_fp"],
            "wasm": cookies["wasm"],
            "cookies": {
                "pr_fp": cookies["pr_fp"],
                "wasm": cookies["wasm"],
            },
            "cookieHeader": f"pr_fp={cookies['pr_fp']}; wasm={cookies['wasm']}",
            "userAgent": self.user_agent,
            "source": "real_chrome_cdp",
            "capture": captured,
        }

    def apply_validation_cookies(self, cookies):
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain=".arbitr.ru", path="/")

    def check_captcha_gate(self):
        return self.session.get(
            f"{BASE_URL}/Recaptcha/IsNeedShowCaptcha",
            params={"_": str(int(time.time() * 1000))},
            headers={
                **self.base_headers(),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{BASE_URL}/",
            },

            verify=False,
            timeout=30,
        )

    def get_captcha_id(self):
        return self.session.get(
            f"{BASE_URL}/Recaptcha/GetCaptchaId",
            params={"_": str(int(time.time() * 1000))},
            headers={
                **self.base_headers(),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{BASE_URL}/",
            },
            timeout=30,
        )

    def get_captcha_image(self, captcha_id):
        return self.session.get(
            f"{BASE_URL}/Recaptcha/GetImage/{captcha_id}",
            params={"_": str(int(time.time() * 1000))},
            headers={
                **self.base_headers(),
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": f"{BASE_URL}/",
            },
            timeout=30,
        )

    def check_captcha(self, captcha_id, text):
        return self.session.get(
            f"{BASE_URL}/Recaptcha/CheckCaptcha",
            params={
                "id": captcha_id,
                "text": text.strip(),
                "_": str(int(time.time() * 1000)),
            },
            headers={
                **self.base_headers(),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{BASE_URL}/",
            },
            timeout=30,
        )

    def search_instances(
            self,
            case_number='А40-60483/2023',
            page=1,
            count=25,
            recaptcha_token=None,
    ):
        payload = {
            "Page": page,
            "Count": count,
            "Courts": [],
            "DateFrom": None,
            "DateTo": None,
            "Sides": [],
            "Judges": [],
            "CaseNumbers": [case_number] if case_number else [],
            "WithVKSInstances": False,
        }
        headers = {
            **self.base_headers(),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
            "x-date-format": "iso",
        }
        if recaptcha_token:
            headers["RecaptchaToken"] = recaptcha_token

        return self.session.post(
            f"{BASE_URL}/Kad/SearchInstances",
            headers=headers,
            data=compact_json(payload).encode("utf-8"),
            timeout=30,
        )

    def get_card(self, card_id_or_url=DEFAULT_CARD_ID):
        if str(card_id_or_url).startswith("http"):
            url = str(card_id_or_url)
        else:
            url = f"{BASE_URL}/Card/{card_id_or_url}"

        return self.session.get(
            url,
            headers={
                **self.base_headers(),
                **self.browser_hint_headers(),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                ),
                "Referer": url,
            },
            timeout=30,
        )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Non-browser kad.arbitr.ru request probe using local fp/wasm cookies."
    )
    parser.add_argument("--case-number", help="Optional case number for /Kad/SearchInstances.")
    parser.add_argument("--recaptcha-token", help="Optional token returned by /Recaptcha/CheckCaptcha.")
    parser.add_argument("--captcha-text", help="Captcha text to submit to /Recaptcha/CheckCaptcha.")
    parser.add_argument("--captcha-image", help="Save captcha image to this path before checking/searching.")
    parser.add_argument("--interactive-captcha", action="store_true", help="Save captcha image and prompt for captcha text in the same session.")
    parser.add_argument("--force-search", action="store_true", help="POST search even when captcha gate says it is required.")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--count", type=int, default=25)
    parser.add_argument("--ua", default=DEFAULT_UA)
    parser.add_argument("--impersonate", default="chrome120")
    parser.add_argument("--proxy", default=DEFAULT_PROXY, help="Proxy URL used for both http and https. Pass an empty string to disable.")
    parser.add_argument("--pr-fp", help="Override the generated pr_fp cookie value.")
    parser.add_argument("--wasm", help="Override the generated wasm cookie value.")
    parser.add_argument("--browser-cookies", action="store_true", help="Use real Chrome/CDP to generate pr_fp/wasm instead of the Node stub helper.")
    parser.add_argument("--browser-headed", action="store_true", help="Run browser cookie capture with a visible Chrome window instead of headless mode.")
    parser.add_argument("--probe-card", action="store_true", help="GET a /Card page after applying pr_fp/wasm and classify the response.")
    parser.add_argument("--card-id", default=DEFAULT_CARD_ID, help="Card id or full card URL for --probe-card.")
    parser.add_argument("--ddg-replay", action="store_true", help="Replay DDoS-Guard id/set/mark before captcha gate.")
    parser.add_argument("--ddg-mark-body", default=str(DDG_MARK_BODY_PATH), help="Path to a captured DDoS-Guard mark request body.")
    parser.add_argument("--save-response", help="Write raw search response body to this path.")
    return parser


def main():
    args = build_parser().parse_args()
    proxy = args.proxy or None
    client = KadClient(user_agent=args.ua, impersonate=args.impersonate, proxy=proxy)

    bootstrap_response = client.bootstrap()
    ddg_summary = None
    if args.ddg_replay:
        ddg_summary, replay_response = client.replay_ddg_challenge(
            f"{BASE_URL}/Version/Change?mode=Full&returnUrl=%2F",
            mark_body_path=args.ddg_mark_body,
        )
        if replay_response is not None:
            bootstrap_response = replay_response

    if args.browser_cookies:
        cookie_info = client.generate_browser_validation_cookies(proxy=proxy, headless=not args.browser_headed)
    else:
        cookie_info = client.generate_validation_cookies()
    cookies_to_apply = dict(cookie_info["cookies"])
    override_sources = {}
    if args.pr_fp:
        cookies_to_apply["pr_fp"] = args.pr_fp
        override_sources["pr_fp"] = "cli"
    if args.wasm:
        cookies_to_apply["wasm"] = args.wasm
        override_sources["wasm"] = "cli"
    print(cookie_info)
    # 同步cookie
    client.apply_validation_cookies(cookies_to_apply)
    print(client.session.cookies.get_dict())

    # IsNeedShowCaptcha - 实际验证请求 - Result 如果为True 会触发图像验证，Result 为False 正常
    captcha_response = client.check_captcha_gate()
    print(captcha_response.text)
    captcha_summary = response_payload(captcha_response)

    output = {
        "bootstrap": response_payload(bootstrap_response, preview=120),
        "validationCookies": {
            "generated_pr_fp": cookie_info.get("pr_fp"),
            "generated_wasm": cookie_info.get("wasm"),
            "applied_pr_fp": cookies_to_apply.get("pr_fp"),
            "applied_wasm": cookies_to_apply.get("wasm"),
            "overrideSources": override_sources,
        },
        "captchaGate": captcha_summary,
    }
    if ddg_summary:
        output["ddgReplay"] = ddg_summary
    output["sessionCookies"] = client.session.cookies.get_dict()

    captcha_required = (
        captcha_summary.get("json", {}).get("Result") is True
        if isinstance(captcha_summary.get("json"), dict)
        else False
    )
    recaptcha_token = args.recaptcha_token

    if captcha_required and not recaptcha_token and (
            args.captcha_text or args.captcha_image or args.interactive_captcha
    ):
        captcha_id_response = client.get_captcha_id()
        captcha_id_summary = response_payload(captcha_id_response)
        output["captchaChallenge"] = {"idResponse": captcha_id_summary}

        captcha_id = (
            captcha_id_summary.get("json", {}).get("Result")
            if isinstance(captcha_id_summary.get("json"), dict)
            else None
        )

        if captcha_id:
            image_path = args.captcha_image
            if args.interactive_captcha and not image_path:
                image_path = str(TARGET_DIR / "samples" / f"captcha_{captcha_id}.png")

            if image_path:
                image_response = client.get_captcha_image(captcha_id)
                output["captchaChallenge"]["imageResponse"] = response_payload(
                    image_response,
                    preview=80,
                )
                if image_response.status_code == 200:
                    save_path = Path(image_path)
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(image_response.content)
                    output["captchaChallenge"]["image_saved_to"] = str(save_path.resolve())

            captcha_text = args.captcha_text
            if args.interactive_captcha:
                print(
                    json.dumps(output["captchaChallenge"], ensure_ascii=False, indent=2),
                    file=sys.stderr,
                )
                captcha_text = input("Captcha text: ").strip()

            if captcha_text:
                check_response = client.check_captcha(captcha_id, captcha_text)
                check_summary = response_payload(check_response)
                output["captchaChallenge"]["checkResponse"] = check_summary
                if (
                        isinstance(check_summary.get("json"), dict)
                        and check_summary["json"].get("Result") is True
                ):
                    recaptcha_token = captcha_id
                    output["captchaChallenge"]["recaptcha_token"] = recaptcha_token

    if args.case_number:
        if captcha_required and not recaptcha_token and not args.force_search:
            output["search"] = {
                "skipped": True,
                "reason": "captcha_required",
                "detail": (
                    "Pass --recaptcha-token, --captcha-text, or use "
                    "--interactive-captcha in the same run. Use --force-search "
                    "only to inspect the server response."
                ),
            }
        else:
            search_response = client.search_instances(
                case_number=args.case_number,
                page=args.page,
                count=args.count,
                recaptcha_token=recaptcha_token,
            )
            print(search_response.text)
            output["search"] = response_payload(search_response, preview=1000)

            if args.save_response:
                save_path = Path(args.save_response)
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(search_response.content)
                output["search"]["saved_to"] = str(save_path.resolve())

    if args.probe_card:
        card_response = client.get_card(args.card_id)
        output["cardProbe"] = response_payload(card_response, preview=1000)
        output["cardProbe"]["classification"] = classify_card_response(card_response)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
