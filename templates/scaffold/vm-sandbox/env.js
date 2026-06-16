// Minimal host environment patch. Keep every field tied to runtime evidence.
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: {
    userAgent: "Mozilla/5.0",
    language: "zh-CN",
    languages: ["zh-CN", "zh"],
    platform: "Win32",
  },
});

Object.defineProperty(globalThis, "location", {
  configurable: true,
  value: {
    href: "https://example.com/",
    origin: "https://example.com",
    protocol: "https:",
    host: "example.com",
    pathname: "/",
  },
});
