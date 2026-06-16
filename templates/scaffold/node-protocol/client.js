import { buildSignature } from "./signer.js";

export async function requestOnce(url, params = {}, headers = {}) {
  const requestParams = new URLSearchParams(params);
  requestParams.set("sign", buildSignature(Object.fromEntries(requestParams.entries())));

  const target = new URL(url);
  for (const [key, value] of requestParams.entries()) {
    target.searchParams.set(key, value);
  }

  const response = await fetch(target, { headers });
  const text = await response.text();
  let body = text;
  try {
    body = JSON.parse(text);
  } catch {
    // Keep raw text for non-JSON responses.
  }

  return {
    status: response.status,
    url: target.toString(),
    body,
  };
}
