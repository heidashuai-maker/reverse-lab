import hashlib
import hmac
import json
from urllib.parse import urlencode


DEFAULT_SECRET = "replace-me"


def canonicalize(value):
    if isinstance(value, dict):
        pairs = []
        for key, item in sorted(value.items()):
            if isinstance(item, (dict, list)):
                item = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
            pairs.append((key, item))
        return urlencode(pairs)
    return str(value)


def build_signature(payload, secret=DEFAULT_SECRET):
    message = canonicalize(payload).encode("utf-8")
    key = secret.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()
