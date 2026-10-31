#!/usr/bin/env node
/*
 * Cloud applicator for public ATS application forms (Greenhouse, Lever, Ashby). No login needed.
 *
 *   node apply_ats.js url     <ats.json>                       -> prints the application-form URL
 *   node apply_ats.js inspect <ats.json> <fields.json>         -> lists every form field (label, type, options, required)
 *   node apply_ats.js submit  <ats.json> <answers.json> <result.json> [--dry-run]
 *
 * ats.json:     {"type": "greenhouse"|"lever"|"ashby", "slug": "...", "id": "..."}
 * answers.json: {"resume": "/abs/path.pdf", "coverLetter": "/abs/path.pdf"?, "fields": [{"key": "<key from inspect>", "value": "..." | true | ["a","b"]}]}
 * result.json:  {"status": "submitted"|"filled"|"blocked", "reason"?, "confirmation"?, "screenshot"}
 *
 * The caller (the daily cloud-apply agent) decides every answer; this script only reads and fills the form.
 */
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const FORM_URL = {
  greenhouse: (a) => `https://job-boards.greenhouse.io/${a.slug}/jobs/${a.id}`,
  lever: (a) => `https://jobs.lever.co/${a.slug}/${a.id}/apply`,
  ashby: (a) => `https://jobs.ashbyhq.com/${a.slug}/${a.id}/application`,
};
const CONFIRM_RE = /thank you for (applying|your application|your interest)|application (has been )?(submitted|received)|we('ve| have) received your application|successfully submitted/i;
const CAPTCHA_RE = /captcha|verify you are human|are you a robot/i;

async function open(ats) {
  const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const page = await browser.newPage({ viewport: { width: 1280, height: 1800 }, locale: "en-US" });
  await page.goto(ats.formUrl || FORM_URL[ats.type](ats), { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  if (ats.type === "ashby") await page.waitForSelector("form, input[type=file]", { timeout: 20000 }).catch(() => {});
  return { browser, page };
}

// Collect every visible input with a human label and a stable key we can find again on a fresh page load.
async function inspect(page) {
  return page.evaluate(() => {
    const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return (r.width > 0 && r.height > 0 && s.visibility !== "hidden") || el.type === "file"; };
    const clean = (t) => (t || "").replace(/\s+/g, " ").replace(/\*$/, "").trim();
    const labelFor = (el) => {
      if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return clean(l.innerText); }
      const wrap = el.closest("label"); if (wrap) return clean(wrap.innerText);
      const by = el.getAttribute("aria-labelledby"); if (by) return clean(by.split(" ").map((i) => document.getElementById(i)?.innerText || "").join(" "));
      if (el.getAttribute("aria-label")) return clean(el.getAttribute("aria-label"));
      const field = el.closest("fieldset, .field, .application-question, [class*=field], [class*=Field], [class*=question]");
      const l = field && field.querySelector("label, legend, .application-label, [class*=label], [class*=Label]");
      return clean(l ? l.innerText : el.placeholder || el.name || "");
    };
    const keyOf = (el) => (el.id ? `#${CSS.escape(el.id)}` : el.name ? `[name="${el.name}"]` : null);
    const out = [], seenGroups = new Set();
    document.querySelectorAll("input, textarea, select").forEach((el) => {
      const type = el.tagName === "SELECT" ? "select" : el.tagName === "TEXTAREA" ? "textarea" : (el.type || "text");
      if (["hidden", "submit", "button", "search"].includes(type) || !visible(el)) return;
      const required = el.required || el.getAttribute("aria-required") === "true" || /\*\s*$/.test((el.closest("label, .field, [class*=field]")?.innerText || "").split("\n")[0]);
      if (type === "radio" || type === "checkbox") {
        const group = el.name || el.closest("fieldset")?.id || labelFor(el);
        if (seenGroups.has(group)) return; seenGroups.add(group);
        const fs = el.closest("fieldset") || el.parentElement.parentElement;
        const opts = [...document.querySelectorAll(`input[name="${CSS.escape(el.name)}"]`)].map((o) => ({ value: o.value, label: labelFor(o) }));
        const legend = fs.querySelector("legend, label, [class*=label]");
        out.push({ key: el.name ? `[name="${el.name}"]` : keyOf(el), type, label: clean(legend ? legend.innerText : labelFor(el)), required, options: opts });
        return;
      }
      const f = { key: keyOf(el), type, label: labelFor(el), required };
      if (el.getAttribute("role") === "combobox" || el.getAttribute("aria-autocomplete")) f.type = "combobox";
      if (type === "select") f.options = [...el.options].map((o) => o.text.trim()).filter(Boolean);
      if (f.key) out.push(f);
    });
    return out;
  });
}

async function fill(page, fields, answers) {
  const byKey = Object.fromEntries(fields.map((f) => [f.key, f]));
  const problems = [];
  for (const { key, value } of answers.fields || []) {
    const f = byKey[key];
    if (!f) { problems.push(`field not found: ${key}`); continue; }
    try {
      const loc = page.locator(key).first();
      if (f.type === "file") continue; // files handled below
      if (f.type === "select") await loc.selectOption({ label: String(value) });
      else if (f.type === "radio") await page.locator(`${key}[value="${value}"]`).first().check({ force: true });
      else if (f.type === "checkbox") {
        const vals = Array.isArray(value) ? value : [value];
        if (vals.length === 1 && typeof vals[0] === "boolean") { vals[0] ? await loc.check({ force: true }) : await loc.uncheck({ force: true }); }
        else for (const v of vals) await page.locator(`${key}[value="${v}"]`).first().check({ force: true });
      } else if (f.type === "combobox") {
        await loc.click(); await loc.fill(String(value)); await page.waitForTimeout(700);
        const opt = page.getByRole("option", { name: String(value), exact: false }).first();
        if (await opt.count()) await opt.click(); else await page.keyboard.press("Enter");
      } else await loc.fill(String(value));
    } catch (e) { problems.push(`${f.label || key}: ${e.message.split("\n")[0]}`); }
  }
  const files = fields.filter((f) => f.type === "file");
  const resumeField = files.find((f) => /resume|cv/i.test(f.label + f.key)) || files[0];
  if (resumeField && answers.resume) await page.setInputFiles(resumeField.key, answers.resume).catch((e) => problems.push(`resume upload: ${e.message}`));
  const coverField = files.find((f) => /cover/i.test(f.label + f.key));
  if (coverField && answers.coverLetter) await page.setInputFiles(coverField.key, answers.coverLetter).catch((e) => problems.push(`cover letter upload: ${e.message}`));
  return problems;
}

async function submit(page) {
  const btn = page.getByRole("button", { name: /submit( application)?|apply|send application/i }).last();
  await btn.scrollIntoViewIfNeeded();
  await btn.click();
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(4000);
  const text = await page.locator("body").innerText();
  if (CONFIRM_RE.test(text)) return { status: "submitted", confirmation: text.match(CONFIRM_RE)[0] };
  if (CAPTCHA_RE.test(text) || (await page.locator("iframe[src*=captcha], iframe[title*=captcha i]").count())) return { status: "blocked", reason: "CAPTCHA" };
  const errs = await page.locator("[class*=error], [role=alert], .invalid-feedback").allInnerTexts();
  return { status: "blocked", reason: errs.filter(Boolean).slice(0, 5).join(" | ") || "No confirmation page after submitting" };
}

(async () => {
  const [mode, atsPath, a2, a3] = process.argv.slice(2);
  const ats = JSON.parse(fs.readFileSync(atsPath, "utf8"));
  if (mode === "url") { console.log(ats.formUrl || FORM_URL[ats.type](ats)); return; }
  const { browser, page } = await open(ats);
  try {
    const fields = await inspect(page);
    if (mode === "inspect") {
      fs.writeFileSync(a2, JSON.stringify({ url: page.url(), title: await page.title(), fields }, null, 1));
      console.log(`${fields.length} fields -> ${a2}`);
      return;
    }
    const answers = JSON.parse(fs.readFileSync(a2, "utf8"));
    const problems = await fill(page, fields, answers);
    const shot = path.join(path.dirname(a3), "form.png");
    await page.screenshot({ path: shot, fullPage: true });
    let result = { status: "filled", problems, screenshot: shot };
    if (!process.argv.includes("--dry-run")) {
      if (problems.length) result = { status: "blocked", reason: problems.join(" | "), screenshot: shot };
      else { result = { ...(await submit(page)), screenshot: path.join(path.dirname(a3), "after-submit.png") }; await page.screenshot({ path: result.screenshot, fullPage: true }); }
    }
    fs.writeFileSync(a3, JSON.stringify(result, null, 1));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch((e) => { console.error(e.message); process.exit(1); });
