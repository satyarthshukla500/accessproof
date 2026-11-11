const chat = document.getElementById("chat");
const msgs = document.getElementById("msgs");
const form = document.getElementById("composer");
const input = document.getElementById("chat-input");
const root = "/order/" + chat.dataset.order + "/help";
const base = root + "?t=" + encodeURIComponent(chat.dataset.token);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

const scroll = () => { msgs.scrollTop = msgs.scrollHeight; };

function add(cls, ...kids) {
  const m = el("div", "msg " + cls);
  m.append(...kids);
  msgs.append(m);
  scroll();
  return m;
}

function receipts(events) {
  const ul = el("ul", "receipts");
  events.forEach((e) => {
    const li = el("li");
    li.append(el("span", "", e.name), el("span", "mono", "#" + e.id + " · " + e.when));
    ul.append(li);
  });
  return ul;
}

function button(label, cls, onclick) {
  const b = el("button", "btn sm " + cls, label);
  b.type = "button";
  b.addEventListener("click", onclick);
  return b;
}

async function solved(id, box) {
  const r = await fetch(root + "/" + id + "/solved", { method: "POST", body: new URLSearchParams({ token: chat.dataset.token }) });
  box.replaceChildren(el("p", "small muted", r.ok ? "Glad that helped. I've noted it for the seller." : "That request is already closed."));
}

function reply(r) {
  msgs.querySelectorAll(".acts").forEach((a) => a.remove());  // buttons only on the latest answer
  const kids = [el("div", "bubble", r.reply)];
  if (r.events && r.events.length) kids.push(receipts(r.events));
  if (r.refund) kids.push(el("p", "small muted", "I've passed a refund request to the seller. A refund only happens if the seller approves it."));
  const acts = el("div", "acts");
  if (r.link) { const a = el("a", "btn sm", "Download again"); a.href = r.link; acts.append(a); }
  if (r.outcome === "resent" || r.outcome === "open") acts.append(button("That solved it", "ghost solved", () => solved(r.id, acts)));
  if (!r.flagged && !r.refund && ["NOT_RECEIVED", "CANT_OPEN", "WANTS_REFUND", "NOT_AS_DESCRIBED"].includes(r.intent)) acts.append(button("Request refund from seller", "ghost", () => send("I'd like a refund, please pass this to the seller.")));
  if (acts.children.length) kids.push(acts);
  add("bot", ...kids);
}

async function send(text) {
  text = text.trim();
  if (!text) return;
  add("me", el("div", "bubble", text));
  input.value = "";
  const typing = el("div", "typing");
  typing.append(el("i"), el("i"), el("i"));
  msgs.append(typing);
  scroll();
  try {
    const r = await fetch(base, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text }) });
    const j = await r.json();
    typing.remove();
    reply(r.ok ? j : { reply: j.error || "Something went wrong. Please try again.", events: [], flagged: true });
  } catch (e) {
    typing.remove();
    reply({ reply: "I could not reach the server. Please try again.", events: [], flagged: true });
  }
}

form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); } });
document.querySelectorAll("#quick button").forEach((b) => b.addEventListener("click", () => send(b.dataset.text)));
document.querySelectorAll(".solved").forEach((b) => b.addEventListener("click", () => solved(b.dataset.id, b.parentElement)));
scroll();
window.addEventListener("load", scroll);
