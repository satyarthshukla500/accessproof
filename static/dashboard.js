const app = document.getElementById("app");
const csrf = app.dataset.csrf;
const $ = (id) => document.getElementById(id);
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
let data = null;
let openId = null;

const VIEWS = {
  overview: ["Command center", "Every sale, provable."],
  orders: ["Orders", "Every order and the state of its proof chain."],
  ledger: ["Proof chains", "Every delivery event, sealed to the next one."],
  help: ["Support chats", "What buyers asked and how the assistant answered."],
  disputes: ["Disputes", "Evidence built from the ledger, reviewed by you."],
};
const STATES = { WAITING_FOR_SELLER_RESPONSE: "Seller to respond", WAITING_FOR_BUYER_RESPONSE: "Buyer to respond", UNDER_REVIEW: "Under review" };
const pretty = (s) => (s ? s.replace(/^MERCHANDISE_OR_SERVICE_/, "").replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase()) : "");
const stateName = (s) => STATES[s] || pretty(s);
const submitted = (d) => d.filed || (d.last_result || "").startsWith("Evidence submitted");
const verdict = (d) => (submitted(d) ? "Evidence submitted" : d.has_pack ? (d.covered ? "Covered" : "Not covered") + (d.source === "paypal" ? " · " + pretty(d.recommendation) : "") : "—");

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

const ICONS = { shield: "M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z M9 12l2 2 4-4", check: "M5 12l4 4 10-10", alert: "M12 3l10 18H2z M12 10v5 M12 18v.01",
  link: "M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1 M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1" };

function svg(name) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("width", "20"); s.setAttribute("height", "20"); s.setAttribute("class", "ico");
  s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "1.8"); s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", ICONS[name]);
  s.append(p);
  return s;
}

function toast(text, bad) {
  const t = el("div", "toast" + (bad ? " bad" : ""));
  t.append(svg(bad ? "alert" : "check"), el("span", "", text));
  $("toasts").append(t);
  setTimeout(() => t.remove(), 4200);
}

function ask(text, label) {
  const d = $("confirm");
  $("confirm-text").textContent = text;
  $("confirm-yes").textContent = label || "Confirm";
  d.showModal();
  return new Promise((done) => d.addEventListener("close", () => done(d.returnValue === "yes"), { once: true }));
}

async function act(url, btn) {
  if (btn) btn.classList.add("busy");
  try {
    const r = await fetch(url, { method: "POST", headers: { "X-CSRF": csrf } });
    const j = await r.json();
    toast(j.message || j.error || "Done", !r.ok);
  } catch (e) {
    toast("Request failed", true);
  }
  if (btn) btn.classList.remove("busy");
  await load();
}

function actButton(label, url, confirmText, cls) {
  const b = el("button", "btn sm " + (cls || ""), label);
  b.type = "button";
  b.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (confirmText && !(await ask(confirmText, label))) return;
    act(url, b);
  });
  return b;
}

function chainEl(blocks, label) {
  const box = el("div", "chain");
  const ol = el("ol", "chain-row");
  blocks.forEach((b, i) => {
    const li = el("li", "block" + (i === blocks.length - 1 ? " last" : ""));
    li.title = b.when;
    li.append(el("span", "num", "Step " + (i + 1)), el("span", "lbl", b.label), el("span", "tm", b.short));
    ol.append(li);
  });
  const v = el("p", "verified");
  v.append(svg("shield"), el("span", "", label || "Record verified"));
  box.append(ol, v);
  return box;
}

function emptyBox(text, ...kids) {
  const b = el("div", "empty");
  b.append(svg("link"), el("p", "", text), ...kids);
  return b;
}

function countUp(node, to, prefix) {
  const from = Number(node.dataset.v || 0);
  node.dataset.v = to;
  if (reduced || from === to) { node.textContent = prefix + to; return; }
  const t0 = performance.now();
  const step = (t) => {
    const k = Math.min((t - t0) / 700, 1);
    node.textContent = prefix + Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

const STATS = [["deflected", "Disputes deflected", "", "buyer clicked “That solved it”"], ["fees", "Est. fees avoided", "$", "at the $15 US dispute fee"],
  ["filed", "Evidence packs filed", "", "sent to PayPal as evidence"], ["refunds", "Refunds approved", "", "approved by you, paid through PayPal"]];

function renderStats() {
  const box = $("stats");
  if (!box.children.length) {
    STATS.forEach(([key, label, , cap]) => {
      const c = el("div", "card stat");
      c.append(el("p", "eyebrow", label), el("p", "num", "0"), el("p", "cap", cap));
      c.dataset.key = key;
      box.append(c);
    });
  }
  STATS.forEach(([key, , prefix]) => countUp(box.querySelector('[data-key="' + key + '"] .num'), data.stats[key], prefix));
}

function renderHero() {
  const box = $("hero");
  box.replaceChildren();
  const d = data.disputes.find((x) => x.source === "paypal");
  if (!d) {
    const sync = actButton("Sync disputes", "/seller/disputes/sync", "", "");
    box.append(el("p", "eyebrow", "Real PayPal dispute"), emptyBox("No real PayPal dispute yet. Sync to bring one in.", sync));
    return;
  }
  const meta = el("div", "hero-meta");
  meta.append(el("span", "pill real", "Real · PayPal sandbox"), el("span", "mono muted", d.id), el("span", "pill sm plain", stateName(d.status)));
  const acts = el("div", "acts");
  if (d.has_pack) { const a = el("a", "btn sm", "Open evidence PDF"); a.href = "/seller/disputes/" + encodeURIComponent(d.id) + "/pdf"; a.target = "_blank"; a.rel = "noopener"; acts.append(a); }
  else acts.append(actButton("Build evidence pack", "/seller/disputes/" + encodeURIComponent(d.id) + "/pack"));
  const claims = el("button", "btn sm ghost", "See cited claims");
  claims.type = "button";
  claims.addEventListener("click", () => openDrawer(d.id));
  acts.append(claims);
  box.append(meta, el("h2", "", "“I never received it” → answered with proof." + (submitted(d) ? " PayPal holds the seller’s evidence." : "")), chainEl(d.chain));
  if (d.summary) box.append(el("p", "muted", d.summary));
  box.append(acts);
}

function renderLists() {
  const feed = $("feed");
  feed.replaceChildren();
  if (!data.feed.length) feed.append(el("li", "none", "Nothing yet. Buy the guide in the store to start the chain."));
  data.feed.slice(0, 7).forEach((f) => {
    const li = el("li");
    const body = el("div");
    body.append(el("b", "", f.text), el("span", "when", f.when));
    li.append(el("i", "dotk " + f.kind), body);
    feed.append(li);
  });
  const tl = $("timeline");
  tl.replaceChildren();
  if (!data.timeline.length) tl.append(el("li", "none", "No proof events yet."));
  data.timeline.forEach((t) => {
    const li = el("li");
    li.append(el("span", "", t.name + " · " + t.when));
    tl.append(li);
  });
}

let view = "overview";
function show(name) {
  if (!VIEWS[name]) name = "overview";
  document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("on", a.id === "tab-" + name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === "panel-" + name));
  $("eyebrow").textContent = VIEWS[name][0];
  $("title").textContent = VIEWS[name][1];
  $("actions").hidden = !["overview", "disputes"].includes(name);
  $("tools").hidden = name === "overview";
  $("qf").value = "";
  view = name;
  document.querySelector(".mobile-only").hidden = name !== "overview";
  if (name !== "overview" && data) Grids.make(name);
  if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
}

/* dispute drawer */
function renderDrawer() {
  const d = data.disputes.find((x) => x.id === openId);
  const drawer = $("drawer");
  if (!d) return;
  const close = el("button", "btn sm ghost", "Close");
  close.type = "button";
  close.addEventListener("click", closeDrawer);
  const title = el("div");
  const src = d.source === "paypal" ? "Real · PayPal sandbox" : d.source === "sample" ? "Sample (not from PayPal)" : "Seed";
  title.append(el("p", "eyebrow", "Dispute"), el("h2", "mono", d.id), el("span", "pill sm plain " + (d.source === "paypal" ? "real" : ""), src));
  const head = el("div", "drawer-head");
  head.append(title, close);
  const body = el("div", "drawer-body");
  const meta = el("dl", "meta");
  [["Reason", pretty(d.reason)], ["Amount", "$" + d.amount], ["State", stateName(d.status)], ["Evidence", verdict(d)], ["Last result", d.last_result || "—"]].forEach(([k, v]) => {
    meta.append(el("dt", "", k), el("dd", "", v));
  });
  const sections = [meta];
  if (d.record.length) {  // PayPal's own list of what was filed on the case
    const rec = el("div");
    rec.append(el("h3", "", "PayPal’s record"));
    const ul = el("ul", "record");
    d.record.forEach((r) => ul.append(el("li", "", r.who + " · " + (r.kind === "Create" ? "opened the case" : r.kind + (r.pdf ? " · PDF on PayPal" : "")) + " · " + r.when)));
    rec.append(ul);
    sections.push(rec);
  }
  const proof = el("div");
  proof.append(el("h3", "", "Proof chain"), chainEl(d.chain));
  sections.push(proof);
  const cl = el("div");
  cl.append(el("h3", "", "Cited claims"));
  if (!d.claims.length) cl.append(el("p", "muted small", "No evidence pack yet. Build one and every claim will cite the ledger events that prove it."));
  const list = el("div", "claims");
  d.claims.forEach((c) => {
    const row = el("div", "claim");
    const evs = el("div", "evs");
    c.event_ids.forEach((id) => { const e = d.events[id]; { const text = el("span", "", e ? e.name + " · " : "event"); if (e) text.append(el("time", "", e.when)); const chip = el("span", "ev"); chip.append(text); evs.append(chip); } });
    row.append(el("p", "", c.text), evs);
    list.append(row);
  });
  cl.append(list);
  if (d.summary) cl.append(el("p", "muted small", d.summary));
  sections.push(cl);
  const acts = el("div", "acts");
  const u = "/seller/disputes/" + encodeURIComponent(d.id);
  if (d.has_pack) { const a = el("a", "btn sm", "Open evidence PDF"); a.href = u + "/pdf"; a.target = "_blank"; a.rel = "noopener"; acts.append(a); } else acts.append(actButton("Build evidence pack", u + "/pack"));
  if (d.can_submit) acts.append(actButton("Submit evidence", u + "/submit", "Submit this evidence pack to PayPal?"));
  if (d.can_offer) acts.append(actButton("Make offer", u + "/offer", "Offer the buyer a full refund of $" + d.amount + "?", "ghost"));
  if (d.can_adjudicate) acts.append(actButton("Simulate decision", u + "/adjudicate", "", "ghost"));
  sections.push(acts);
  body.append(...sections);
  drawer.replaceChildren(head, body);
  return close;
}

function openDrawer(id) {
  openId = id;
  const close = renderDrawer();
  $("drawer").classList.add("open");
  $("drawer").setAttribute("aria-hidden", "false");
  $("scrim").classList.add("open");
  if (close) close.focus();
}

function closeDrawer() {
  openId = null;
  $("drawer").classList.remove("open");
  $("drawer").setAttribute("aria-hidden", "true");
  $("scrim").classList.remove("open");
}

async function load() {
  try {
    const r = await fetch("/api/data");
    data = await r.json();
  } catch (e) {
    toast("Session expired. Reload the page and sign in again.", true);
    return;
  }
  renderStats();
  renderHero();
  renderLists();
  Grids.refresh();
  if (openId) renderDrawer();
}

document.querySelectorAll(".nav a").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); show(a.id.slice(4)); }));
$("scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && openId) closeDrawer(); });
$("qf").addEventListener("input", (e) => Grids.filter(view, e.target.value));
$("csv").addEventListener("click", () => Grids.csv(view));
$("sync").addEventListener("click", (e) => act("/seller/disputes/sync", e.currentTarget));
$("sample").addEventListener("click", (e) => act("/seller/disputes/sample", e.currentTarget));
$("sample-snad").addEventListener("click", (e) => act("/seller/disputes/sample?reason=snad", e.currentTarget));
window.addEventListener("hashchange", () => show(location.hash.slice(1)));
document.addEventListener("DOMContentLoaded", async () => {
  await load();
  show((location.hash || "#overview").slice(1));
});
