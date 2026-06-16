import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from signer import build_signature


def request_once(url, params=None, headers=None, timeout=20):
    params = dict(params or {})
    headers = dict(headers or {})
    params["sign"] = build_signature(params)

    target = url
    if params:
        separator = "&" if "?" in url else "?"
        target = f"{url}{separator}{urlencode(params)}"

    req = Request(target, headers=headers, method="GET")
    with urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = text
        return {
            "status": resp.status,
            "url": target,
            "body": body,
        }
