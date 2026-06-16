import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { requestOnce } from "./client.js";
import { buildSignature } from "./signer.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturesPath = path.join(__dirname, "fixtures.json");

function readFixtures() {
  if (!fs.existsSync(fixturesPath)) return { cases: [] };
  return JSON.parse(fs.readFileSync(fixturesPath, "utf8"));
}

function getArg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : "";
}

function selfTest() {
  const fixtures = readFixtures();
  let failed = 0;
  for (const [index, item] of fixtures.cases.entries()) {
    const actual = buildSignature(item.input || {});
    if (item.expectedSignature && actual !== item.expectedSignature) {
      failed += 1;
      console.error(`case ${index + 1}: mismatch expected=${item.expectedSignature} actual=${actual}`);
    } else {
      console.log(`case ${index + 1}: ok signature=${actual}`);
    }
  }
  if (!fixtures.cases.length) console.log("No fixture cases yet.");
  return failed ? 1 : 0;
}

if (process.argv.includes("--self-test")) {
  process.exit(selfTest());
}

if (process.argv.includes("--once")) {
  const url = getArg("--url");
  if (!url) {
    console.error("--url is required with --once");
    process.exit(1);
  }
  const result = await requestOnce(url);
  console.log(JSON.stringify(result, null, 2));
} else {
  console.log("Usage: node main.js --self-test | --once --url <url>");
}
