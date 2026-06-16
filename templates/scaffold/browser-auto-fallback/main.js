import fs from "node:fs";
import path from "node:path";
import { chromium, firefox } from "playwright-core";

function getArg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : "";
}

function readConfig() {
  const file = path.join(process.cwd(), "config.json");
  if (!fs.existsSync(file)) return {};
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

const config = readConfig();
const url = getArg("--url") || config.url;
if (!url) {
  console.error("Missing --url or config.url");
  process.exit(1);
}

const family = config.browserFamily || "chromium";
const browserType = family === "firefox" ? firefox : chromium;
const browser = await browserType.launch({
  headless: config.headless !== false,
  executablePath: config.executablePath || undefined,
});

const context = await browser.newContext({
  userAgent: config.userAgent || undefined,
  locale: config.locale || "zh-CN",
});
const page = await context.newPage();
const responses = [];
page.on("response", (response) => {
  responses.push({ url: response.url(), status: response.status() });
});

await page.goto(url, { waitUntil: "domcontentloaded", timeout: config.timeout || 30000 });
await page.waitForTimeout(config.settleMs || 3000);

fs.mkdirSync("screenshots", { recursive: true });
await page.screenshot({ path: "screenshots/latest.png", fullPage: true });
console.log(JSON.stringify({ url: page.url(), title: await page.title(), responses }, null, 2));

await browser.close();
