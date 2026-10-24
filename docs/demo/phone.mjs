// The phone page at phone size, recorded as a video (CDP screencast) through
// a real flow: the list, a VM, a task typed and given, the agent working on
// it live, its runs. Writes OUT/frames/NNNNN.jpg, OUT/frames.json (when each
// frame came) and OUT/marks.json (captions and speed-ups); make.sh puts them
// together.
import { spawn } from "node:child_process";
import { writeFileSync, mkdtempSync, mkdirSync } from "node:fs";

const out = process.argv[2], url = process.argv[3];
const task = "In ~/demo, add a function to src/cart.py that applies a discount code, with a test. Run the tests.";
mkdirSync(`${out}/frames`, { recursive: true });
const chrome = spawn("chromium", ["--headless=new", "--remote-debugging-port=9335", "--no-first-run",
  "--user-data-dir=" + mkdtempSync(out + "/prof-"), "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, id = 0;
const pending = new Map(), frames = [], marks = [];
const t0 = Date.now(), now = () => (Date.now() - t0) / 1000;
const mark = (caption, speed = 1) => { marks.push({ t: now(), caption, speed }); console.log("mark", caption); };
const cmd = (method, params = {}) => new Promise(res => {
  const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params }));
});
const ev = async expr => (await cmd("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result.result.value;
async function until(expr, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await ev(expr)) return true; await sleep(400); }
  return false;
}
// A ring where the finger lands, then the click.
const TAP = `window.tap = el => { const r = el.getBoundingClientRect(), d = document.createElement("div");
  d.style.cssText = "position:fixed;z-index:99999;pointer-events:none;width:44px;height:44px;border-radius:50%;" +
    "background:rgba(156,194,143,.45);border:2px solid #9cc28f;transition:transform .45s,opacity .45s;" +
    "left:" + (r.left + r.width / 2 - 22) + "px;top:" + (r.top + r.height / 2 - 22) + "px";
  document.body.appendChild(d); requestAnimationFrame(() => { d.style.transform = "scale(1.6)"; d.style.opacity = "0"; });
  setTimeout(() => d.remove(), 600); setTimeout(() => el.click(), 250); }; true`;
const tap = async sel => { await ev(`tap(${sel})`); await sleep(900); };
async function type(sel, text) {
  await ev(`${sel}.focus()`);
  for (let i = 1; i <= text.length; i++) {
    await ev(`(e => { e.value = ${JSON.stringify(text.slice(0, i))}; e.dispatchEvent(new Event("input")); })(${sel})`);
    await sleep(35);
  }
}
try {
  let list;
  for (let i = 0; i < 50; i++) { try { list = await (await fetch("http://127.0.0.1:9335/json")).json(); break; } catch (e) { await sleep(200); } }
  ws = new WebSocket(list.find(t => t.type === "page").webSocketDebuggerUrl);
  ws.onmessage = m => {
    const d = JSON.parse(m.data);
    if (d.method === "Page.screencastFrame") {
      const n = frames.length;
      writeFileSync(`${out}/frames/${String(n).padStart(5, "0")}.jpg`, Buffer.from(d.params.data, "base64"));
      frames.push(now());
      ws.send(JSON.stringify({ id: ++id, method: "Page.screencastFrameAck", params: { sessionId: d.params.sessionId } }));
    } else if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
  };
  await new Promise(r => ws.onopen = r);
  await cmd("Emulation.setDeviceMetricsOverride", { width: 390, height: 720, deviceScaleFactor: 2, mobile: true });
  await cmd("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
  await cmd("Page.enable");
  await cmd("Page.navigate", { url });
  await until(`document.querySelectorAll(".vm").length > 0`, 30000);
  await ev(TAP);
  await sleep(800);
  await cmd("Page.startScreencast", { format: "jpeg", quality: 90, everyNthFrame: 1 });
  mark("Your VMs, on the phone");
  await sleep(2000);
  await tap(`[...document.querySelectorAll(".vm")].find(c => c.querySelector(".name").textContent === "arch").querySelector(".head")`);
  mark("Give one a task");
  await sleep(1000);
  await ev(`document.getElementById("task").scrollIntoView({block: "center"})`);
  await sleep(600);
  await type(`document.getElementById("task")`, task);
  await sleep(700);
  await tap(`document.getElementById("task-go")`);
  await until(`view === "term"`, 120000);
  mark("The agent works on it in the VM; you watch, live", 5);
  for (let i = 0; i < 3; i++) await tap(`document.getElementById("bigger")`);
  await until(`!document.getElementById("ended").classList.contains("hidden")`, 240000);
  mark("Done", 1);
  await sleep(3500);
  mark("Its runs, and a notification when one ends");
  await ev(`history.back()`);
  await sleep(800);
  await ev(`document.getElementById("runs").scrollIntoView({block: "center"})`);
  await sleep(3500);
  mark("end");
  await cmd("Page.stopScreencast");
} finally {
  writeFileSync(`${out}/frames.json`, JSON.stringify(frames));
  writeFileSync(`${out}/marks.json`, JSON.stringify(marks));
  chrome.kill();
  process.exit(0);
}
