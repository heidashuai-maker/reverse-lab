import argparse
import json
import sys
from pathlib import Path

from kad_request import (
    DEFAULT_CARD_ID,
    DEFAULT_PROXY,
    DEFAULT_RESPONSE_PATH,
    DEFAULT_UA,
    generate_cookies,
    request_card,
    response_summary,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def build_parser():
    parser = argparse.ArgumentParser(description="Small smoke test for the local JS cookie helper.")
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    parser.add_argument("--ua", default=DEFAULT_UA)
    parser.add_argument("--card-id", default=DEFAULT_CARD_ID)
    parser.add_argument("--save-response", default=str(DEFAULT_RESPONSE_PATH))
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--verify-tls", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()
    cookies = generate_cookies(args.ua)
    response = request_card(
        args.card_id,
        cookies,
        proxy=args.proxy or None,
        timeout=args.timeout,
        verify_tls=args.verify_tls,
    )
    output = {
        "source": "node_js_helper",
        "cookies": {
            "pr_fp": cookies["pr_fp"],
            "wasm": cookies["wasm"],
        },
        "cardProbe": response_summary(response, Path(args.save_response)),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
