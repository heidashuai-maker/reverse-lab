import argparse
import json
from pathlib import Path

from client import request_once
from signer import build_signature


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures.json"


def load_fixtures():
    if not FIXTURES.exists():
        return {"cases": []}
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def self_test():
    fixtures = load_fixtures()
    cases = fixtures.get("cases", [])
    if not cases:
        print("No fixture cases yet.")
        return 0

    failed = 0
    for index, case in enumerate(cases, 1):
        actual = build_signature(case.get("input", {}))
        expected = case.get("expectedSignature")
        if expected and actual != expected:
            failed += 1
            print(f"case {index}: mismatch expected={expected} actual={actual}")
        else:
            print(f"case {index}: ok signature={actual}")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--url", default="")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(self_test())

    if args.once:
        if not args.url:
            raise SystemExit("--url is required with --once")
        result = request_once(args.url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
