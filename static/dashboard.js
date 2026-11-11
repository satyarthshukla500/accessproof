const csrf = document.getElementById("app").dataset.csrf;
const statusEl = document.getElementById("status");
const grids = {};
let data = null;

function el(tag, text, cls) {
  const e = document.createElement(tag);
  e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

async function act(url, label) {
  statusEl.textContent = label + "...";
  try {
    const r = await fetch(url, { method: "POST", headers: { "X-CSRF": csrf } });
    const j = await r.json();
    statusEl.textContent = j.message || j.error || "Done";
    statusEl.className = "status " + (r.ok ? "ok" : "danger");
  } catch (e) {
    statusEl.textContent = "Request failed";
    statusEl.className = "status danger";
  }
  load();
}

function button(label, url, confirmText) {
  const b = el("button", label, "btn small");
  b.style.marginRight = "4px";
  b.addEventListener("click", async () => {
    if (confirmText && !confirm(confirmText)) return;
    b.disabled = true;
    await act(url, label);
  });
  return b;
}

// Builds a grid cell from a list of DOM nodes (text only, never innerHTML)
function cell(build) {
  return (p) => {
    const box = document.createElement("span");
    build(p.data).forEach((n) => box.appendChild(n));
    return box;
  };
}

const pretty = (s) => (s ? s.replace(/^MERCHANDISE_OR_SERVICE_/, "").replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase()) : "");
const stateNames = { WAITING_FOR_SELLER_RESPONSE: "Seller to respond", WAITING_FOR_BUYER_RESPONSE: "Buyer to respond", UNDER_REVIEW: "Under review" };
const state = (s) => stateNames[s] || pretty(s);
const intents = { NOT_RECEIVED: "Not received", CANT_OPEN: "Can't open", WANTS_REFUND: "Wants refund", NOT_AS_DESCRIBED: "Not as described", OTHER: "Other" };
const actions = { RESEND: "Re-sent link", OFFER_REFUND: "Refund suggested", NONE: "None" };
const submitted = (r) => (r.last_result || "").startsWith("Evidence submitted");
const verdict = (r) => (submitted(r) ? "Evidence submitted" : r.has_pack ? (r.covered ? "Covered" : "Not covered") + (r.source === "paypal" ? " · " + pretty(r.recommendation) : "") : "—");
const isMobile = window.innerWidth < 900;
const source = { field: "source", headerName: "Source", width: 110, cellRenderer: (p) => (p.value && p.value !== "real" ? el("span", p.value, "badge") : "") };
const chain = { field: "chain", headerName: "Chain", width: 100, cellRenderer: (p) => el("span", p.value === "ok" ? "Verified" : "BROKEN", p.value === "ok" ? "" : "danger") };

function disputeId(r) {
  const label = r.source === "paypal" ? "Real · PayPal sandbox" : r.source === "sample" ? "Sample (not from PayPal)" : "Seed";
  const box = el("div", "", "stack");
  box.append(el("span", r.id), el("span", label, r.source === "paypal" ? "badge real" : "badge"));
  return box;
}

// Phone layout: one stacked cell per dispute plus its buttons, so nothing needs sideways scrolling
const phoneDisputes = [
  { headerName: "Dispute", flex: 1, minWidth: 170, autoHeight: true, wrapText: true, cellRenderer: cell((r) => {
    const box = disputeId(r);
    box.append(el("span", pretty(r.reason) + " · $" + r.amount, "small"), el("span", state(r.status) + " · " + verdict(r), "small muted"));
    return [box];
  }) },
  { headerName: "Actions", width: 170, autoHeight: true, cellRenderer: cell((r) => {
    const box = el("div", "", "stack gap");
    box.append(...disputeActions(r));
    return [box];
  }) },
];

function disputeActions(r) {
  const u = "/seller/disputes/" + encodeURIComponent(r.id);
  const out = [];
  if (!r.has_pack) {
    out.push(button("Build evidence pack", u + "/pack"));
  } else {
    const a = el("a", "View PDF", "btn small ghost");
    a.href = u + "/pdf";
    a.target = "_blank";
    a.style.marginRight = "4px";
    out.push(a);
    if (r.can_submit) out.push(button("Submit evidence", u + "/submit", "Submit this evidence pack to PayPal?"));
  }
  if (r.can_offer) out.push(button("Make offer", u + "/offer", "Offer the buyer a full refund of $" + r.amount + "?"));
  if (r.can_adjudicate) out.push(button("Simulate decision", u + "/adjudicate"));
  return out;
}

const defs = {
  orders: { empty: "No orders yet. Buy the product in the store to see one.", cols: [
    { field: "id", headerName: "Order", flex: 1, minWidth: 160 }, { field: "capture_id", headerName: "Capture ID", flex: 1, minWidth: 160 },
    { field: "payer_email", headerName: "Payer", flex: 1, minWidth: 160 }, { field: "amount", headerName: "Amount", width: 100 },
    { field: "when", headerName: "Created", width: 200 }, chain, source] },
  ledger: { empty: "No access events yet.", cols: [
    { field: "id", headerName: "ID", width: 80 }, { field: "when", headerName: "Time", width: 190 },
    { field: "event", headerName: "Event", width: 210 }, { field: "order_id", headerName: "Order", minWidth: 160 },
    { field: "ip", headerName: "IP", width: 130, valueFormatter: (p) => p.value || "—" }, { field: "ua", headerName: "User agent", flex: 1, minWidth: 160, valueFormatter: (p) => p.value || "—" }, chain] },
  help: { empty: "No help requests yet.", cols: [
    { field: "id", headerName: "ID", width: 70 }, { field: "message", headerName: "Buyer message", flex: 1, minWidth: 200 },
    { field: "intent", headerName: "Intent", width: 150, valueFormatter: (p) => intents[p.value] || p.value },
    { field: "action", headerName: "Action", width: 150, valueFormatter: (p) => actions[p.value] || p.value },
    { field: "outcome", headerName: "Outcome", width: 140, valueFormatter: (p) => pretty(p.value) },
    { field: "flagged", headerName: "Flagged", width: 100, valueFormatter: (p) => (p.value ? "Flagged" : "") },
    { headerName: "Refund", width: 170, cellRenderer: cell((r) => (["pending", "failed"].includes(r.refund_status)
      ? [button("Approve refund", "/seller/refund/" + r.refund_id + "/approve", "Refund the buyer? This sends a real sandbox refund.")] : [el("span", r.refund_status || "")])) },
    source] },
  disputes: { empty: "No disputes yet. Sync from PayPal or load a sample.", cols: [
    { headerName: "Dispute", width: 190, cellRenderer: cell((r) => [disputeId(r)]) },
    { headerName: "Reason", width: 180, valueGetter: (p) => pretty(p.data.reason) + " · $" + p.data.amount },
    { field: "status", headerName: "State", width: 140, valueFormatter: (p) => state(p.value) },
    { headerName: "Evidence", width: 190, valueGetter: (p) => verdict(p.data) },
    { headerName: "Actions", width: 200, cellRenderer: cell(disputeActions) },
    { field: "last_result", headerName: "Last result", minWidth: 190, flex: 1, tooltipField: "last_result" }] },
};

function show(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.id === "tab-" + name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === "panel-" + name));
  if (!grids[name]) {
    const d = defs[name];
    grids[name] = agGrid.createGrid(document.getElementById("grid-" + name), {
      columnDefs: isMobile && name === "disputes" ? phoneDisputes : d.cols, rowData: data[name], defaultColDef: { sortable: true, filter: true, resizable: true },
      overlayNoRowsTemplate: "<span>" + d.empty + "</span>", rowHeight: isMobile && name === "disputes" ? undefined : 48,
    });
  }
}

async function load() {
  try {
    data = await (await fetch("/api/data")).json();
  } catch (e) {
    statusEl.textContent = "Session expired. Reload the page and log in again.";
    return;
  }
  document.getElementById("s-deflected").textContent = data.stats.deflected;
  document.getElementById("s-fees").textContent = "$" + data.stats.fees;
  document.getElementById("s-filed").textContent = data.stats.filed;
  Object.keys(grids).forEach((n) => grids[n].setGridOption("rowData", data[n]));
}

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => show(t.id.slice(4))));
document.getElementById("sync").addEventListener("click", () => act("/seller/disputes/sync", "Syncing"));
document.getElementById("sample").addEventListener("click", () => act("/seller/disputes/sample", "Adding sample"));
document.getElementById("sample-snad").addEventListener("click", () => act("/seller/disputes/sample?reason=snad", "Adding sample"));
window.addEventListener("load", async () => {
  await load();
  show("orders");
});
