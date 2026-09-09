import { spawn } from "node:child_process";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const appUrl = process.env.APP_URL || "http://127.0.0.1:8000";
const chromePath = process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 9300 + Math.floor(Math.random() * 300);
const profile = await mkdtemp(join(tmpdir(), "career-browser-"));
const chrome = spawn(chromePath, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--force-prefers-reduced-motion", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "about:blank"
], { stdio: "ignore", windowsHide: true });

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function targets() {
  for (let attempt = 0; attempt < 50; attempt++) {
    try { return await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); }
    catch { await sleep(100); }
  }
  throw new Error("Chrome DevTools did not start");
}

await targets();
const target = await (await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(appUrl)}`, { method: "PUT" })).json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.addEventListener("open", resolve); socket.addEventListener("error", reject); });
let nextId = 1;
const pending = new Map();
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id); pending.delete(message.id);
    message.error ? reject(new Error(message.error.message)) : resolve(message.result);
  }
});
function cdp(method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => { pending.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params })); });
}
async function evaluate(expression) {
  const result = await cdp("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}
async function waitFor(expression, timeout = 15000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    if (await evaluate(expression)) return;
    await sleep(80);
  }
  throw new Error(`Timed out: ${expression}`);
}
async function setViewport(width, height) {
  await cdp("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 768 });
}
async function assertPage(label, expression) {
  const result = await evaluate(expression);
  if (!result) throw new Error(`Browser assertion failed: ${label}`);
  process.stdout.write(`ok - ${label}\n`);
}

try {
  await cdp("Page.enable"); await cdp("Runtime.enable"); await setViewport(390, 844);
  await cdp("Page.navigate", { url: appUrl });
  await waitFor(`location.href.startsWith(${JSON.stringify(appUrl)}) && document.readyState === 'complete'`);
  await waitFor("!!document.querySelector('[data-action=\"begin\"]')");
  await assertPage("390px landing has no horizontal overflow", "document.documentElement.scrollWidth <= window.innerWidth");
  await assertPage("landing primary action is visible", "!!document.querySelector('[data-action=begin]').offsetParent");
  await evaluate("document.querySelector('[data-action=begin]').click()"); await waitFor("document.querySelector('#screen-onboarding').classList.contains('active')");
  await waitFor("document.querySelector('#industry').options.length > 1 && document.querySelector('#career-stage').options.length > 1");
  await assertPage("onboarding labels every required control", "[...document.querySelectorAll('#profile-form input[required],#profile-form select[required]')].every(x=>!!document.querySelector(`label[for=${x.id}]`))");
  await evaluate(`(() => {
    const set=(id,value)=>{const e=document.querySelector(id);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));};
    set('#first-name','BrowserTest');document.querySelector('[data-action="custom-career"]').click();
    set('#custom-career','solar irrigation repairer and farm adviser');set('#career-stage','Career changer');
    const industry=document.querySelector('#industry');industry.value=[...industry.options].find(o=>o.value==='Engineering')?.value||industry.options[1].value;
    document.querySelector('#profile-form').requestSubmit();
  })()`);
  await waitFor("document.querySelector('#screen-avatar').classList.contains('active')");
  await evaluate("document.querySelector('[data-action=skip-avatar]').click();document.querySelector('[data-action=start-assessment]').click()");
  await waitFor("document.querySelector('#screen-assessment').classList.contains('active')");
  for (let index = 0; index < 18; index++) {
    if (await evaluate("document.querySelector('#screen-scan').classList.contains('active') || document.querySelector('#screen-battle').classList.contains('active')")) break;
    await waitFor("!!document.querySelector('.answer-option:not([disabled])')");
    await evaluate("document.querySelector('.answer-option:not([disabled])').click()"); await sleep(100);
  }
  await waitFor("document.querySelector('#screen-battle').classList.contains('active')", 20000);
  await assertPage("battle retains verdict, HP, and threat cards", "document.querySelectorAll('.threat-card').length >= 1 && !!document.querySelector('.hp-board')");
  await evaluate("document.querySelector('[data-action=brace]').click()"); await waitFor("!document.querySelector('#skill-combat').classList.contains('hidden')");
  for (let index = 0; index < 3; index++) { await waitFor("!!document.querySelector('#combat-card .button')"); await evaluate("document.querySelector('#combat-card .button').click()"); await sleep(80); }
  await waitFor("!document.querySelector('#results-actions').classList.contains('hidden')");await evaluate("document.querySelector('[data-action=view-results]').click()");await waitFor("document.querySelector('#screen-results').classList.contains('active')");
  await assertPage("results expose seven dimensions", "document.querySelectorAll('.dimension-card').length === 7");
  await assertPage("results contain career-specific skill quests", "document.querySelectorAll('.skill-card').length >= 3");
  await assertPage("results offer an email capture with a consent checkbox", "!!document.querySelector('#email-form') && !!document.querySelector('#results-consent')");
  await evaluate("(()=>{const e=document.querySelector('#results-email');e.value='browser.test@example.com';e.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#email-form').requestSubmit();})()");
  await waitFor("document.querySelector('.email-capture').classList.contains('done')", 15000);
  await assertPage("emailing results confirms in place", "!!document.querySelector('.email-sent')");

  for (const [width, height] of [[320, 720], [375, 812], [390, 844], [768, 1024], [1024, 768], [1440, 900]]) {
    await setViewport(width, height); await sleep(60);
    await assertPage(`${width}px results have no horizontal overflow`, "document.documentElement.scrollWidth <= window.innerWidth");
    await assertPage(`${width}px visible buttons meet touch target height`, "[...document.querySelectorAll('button')].filter(x=>x.offsetParent).every(x=>x.getBoundingClientRect().height>=44)");
  }
  process.stdout.write("Browser critical path complete.\n");
} finally {
  socket.close(); chrome.kill();
}
