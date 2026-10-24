// The phone page at phone size, through a real flow: the list, the
// notifications box, a VM, a task given and followed, Claude Code.
import { spawn } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";

const out = process.argv[2], url = process.argv[3];
const chrome = spawn("chromium", ["--headless=new", "--remote-debugging-port=9335", "--no-first-run",
  "--user-data-dir=" + mkdtempSync(out + "/prof-"), "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, id = 0;
const pending = new Map();
const cmd = (method, params = {}) => new Promise(res => {
  const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params }));
});
const ev = async expr => (await cmd("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result.result.value;
async function shot(name) {
  await sleep(600);
  const r = await cmd("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${out}/${name}.png`, Buffer.from(r.result.data, "base64"));
  console.log("shot", name);
}
async function until(expr, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await ev(expr)) return true; await sleep(500); }
  return false;
}
try {
  let list;
  for (let i = 0; i < 50; i++) { try { list = await (await fetch("http://127.0.0.1:9335/json")).json(); break; } catch (e) { await sleep(200); } }
  ws = new WebSocket(list.find(t => t.type === "page").webSocketDebuggerUrl);
  ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
  await new Promise(r => ws.onopen = r);
  await cmd("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await cmd("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
  await cmd("Page.enable");
  await cmd("Page.navigate", { url });
  await until(`document.querySelectorAll(".vm").length > 0`, 30000);
  await shot("p1-list");
  await ev(`window.scrollTo(0, 5000)`);
  await until(`document.querySelector("#notes-body code") !== null`, 15000);
  await shot("p2-notes");
  await ev(`window.scrollTo(0, 0); [...document.querySelectorAll(".vm")].find(c => c.querySelector(".name").textContent === "arch").querySelector(".head").click()`);
  await sleep(2500);
  await shot("p3-vm");
  await ev(`document.getElementById("task").value = "Add a function that formats a cart total as euros, with a test."`);
  await shot("p4-task");
  await ev(`document.getElementById("task-go").click()`);
  await until(`view === "term"`, 120000);
  await sleep(30000);
  await shot("p5-log");
  await ev(`history.back()`);
  await sleep(3000);
  await ev(`document.getElementById("runs").scrollIntoView({block: "center"})`);
  await sleep(1500);
  await shot("p6-runs");
  await ev(`window.scrollTo(0, 0); document.querySelector("#vm-open .primary").click()`);
  await sleep(9000);
  await shot("p7-claude");
} finally {
  chrome.kill();
  process.exit(0);
}
