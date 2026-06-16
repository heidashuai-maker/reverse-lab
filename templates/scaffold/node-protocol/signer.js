import crypto from "node:crypto";

const DEFAULT_SECRET = "replace-me";

export function canonicalize(value) {
  return Object.entries(value)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, val]) => `${encodeURIComponent(key)}=${encodeURIComponent(typeof val === "object" ? JSON.stringify(val) : String(val))}`)
    .join("&");
}

export function buildSignature(payload, secret = DEFAULT_SECRET) {
  return crypto.createHmac("sha256", secret).update(canonicalize(payload), "utf8").digest("hex");
}
