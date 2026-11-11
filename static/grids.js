/* AG Grid tables for the seller dashboard (helpers come from dashboard.js) */
const Grids = (() => {
  const grids = {};
  const seen = {};
  const fresh = {};
  const phone = window.innerWidth < 900;
  const EVENTS = { PURCHASE_CAPTURED: "Payment captured", DELIVERY_EMAIL_LOGGED: "Download link issued", LINK_OPENED: "Link opened", FILE_DOWNLOADED: "File downloaded",
    LINK_RESENT: "New link issued", REFUND_APPROVED: "Refund approved", EVIDENCE_SUBMITTED: "Evidence submitted" };
  const INTENTS = { NOT_RECEIVED: "Not received", CANT_OPEN: "Can't open", WANTS_REFUND: "Wants refund", NOT_AS_DESCRIBED: "Not as described", OTHER: "Other" };
  const ACTIONS = { RESEND: "Re-sent link", OFFER_REFUND: "Refund suggested", NONE: "None" };
  const OUTCOMES = { deflected: "p-ok", refunded: "p-ok", resent: "", refund_pending: "p-warn", escalated: "p-warn", open: "" };

  const pill = (text, cls) => el("span", "pill sm plain " + (cls || ""), text);
  const cell = (build) => (p) => { const box = el("span", "cellbtn"); build(p.data).forEach((n) => box.append(n)); return box; };
  const stack = (...kids) => { const box = el("div", "stack"); box.append(...kids); return box; };
  const sourcePill = (s) => (s === "paypal" ? pill("Real · PayPal sandbox", "p-real") : s === "sample" ? pill("Sample (not from PayPal)", "p-sample") : s === "seed" ? pill("Seed", "p-seed") : "");
  const demoPill = (s) => (s === "seed" || s === "sample" ? pill(s === "seed" ? "Seed" : "Sample", s === "seed" ? "p-seed" : "p-sample") : "");
  const dash = (p) => p.value || "—";
  const chainPill = (v) => pill(v === "ok" ? "Verified" : "Broken", v === "ok" ? "p-ok" : "p-warn");
  const chain = { field: "chain", headerName: "Chain", width: 110, cellRenderer: (p) => chainPill(p.value) };
  const idCell = (r, label) => stack(el("span", "mono", label), demoPill(r.source));

  function disputeActions(r) {
    const u = "/seller/disputes/" + encodeURIComponent(r.id);
    const out = [];
    if (!r.has_pack) out.push(actButton(phone ? "Build pack" : "Build evidence pack", u + "/pack"));
    else { const a = el("a", "btn sm ghost", "View PDF"); a.href = u + "/pdf"; a.target = "_blank"; a.rel = "noopener"; a.addEventListener("click", (e) => e.stopPropagation()); out.push(a); }
    if (r.can_submit) out.push(actButton("Submit evidence", u + "/submit", "Submit this evidence pack to PayPal?"));
    if (r.can_offer) out.push(actButton("Make offer", u + "/offer", "Offer the buyer a full refund of $" + r.amount + "?", "ghost"));
    if (r.can_adjudicate) out.push(actButton("Simulate decision", u + "/adjudicate", "", "ghost"));
    return out;
  }

  const refundCell = cell((r) => (["pending", "failed"].includes(r.refund_status)
    ? [actButton("Approve refund", "/seller/refund/" + r.refund_id + "/approve", "Approve this refund? It is paid through PayPal (sandbox).")] : [el("span", "muted", r.refund_status || "")]));
  const reasonCell = cell((r) => [stack(el("span", "", pretty(r.reason)), el("span", "muted small", "$" + r.amount))]);
  const disputeId = cell((r) => { const box = el("div", "stack"); box.append(el("span", "mono", r.id), sourcePill(r.source)); return [box]; });

  const DEFS = {
    orders: [{ headerName: "Order", width: 230, cellRenderer: cell((r) => [idCell(r, r.id)]) }, { field: "payer_email", headerName: "Payer", flex: 1, minWidth: 190, tooltipField: "payer_email" },
      { field: "amount", headerName: "Amount", width: 100, type: "rightAligned", valueFormatter: (p) => "$" + p.value }, { field: "when", headerName: "Created", width: 205 }, chain],
    ledger: [{ field: "id", headerName: "ID", width: 90, cellClass: "mono", valueFormatter: (p) => "#" + p.value }, { field: "when", headerName: "Time", width: 205 },
      { field: "event", headerName: "Event", flex: 1, minWidth: 190, tooltipField: "ua", valueFormatter: (p) => EVENTS[p.value] || p.value }, { field: "order_id", headerName: "Order", width: 190, cellClass: "mono" },
      { field: "ip", headerName: "IP", width: 120, valueFormatter: dash }, chain],
    help: [{ headerName: "ID", width: 100, cellRenderer: cell((r) => [idCell(r, "#" + r.id)]) }, { field: "message", headerName: "Buyer message", flex: 2, minWidth: 220, wrapText: true, autoHeight: true, tooltipField: "message" },
      { field: "intent", headerName: "Intent", width: 140, valueFormatter: (p) => INTENTS[p.value] || p.value },
      { field: "outcome", headerName: "Outcome", width: 150, cellRenderer: (p) => pill(pretty(p.value), OUTCOMES[p.value]) },
      { field: "flagged", headerName: "Flag", width: 100, sortable: false, filter: false, cellRenderer: (p) => (p.value ? pill("Flagged", "p-warn") : "") }, { headerName: "Refund", width: 170, sortable: false, filter: false, cellRenderer: refundCell }],
    disputes: [{ headerName: "Dispute", width: 210, cellRenderer: disputeId }, { headerName: "Reason", width: 150, cellRenderer: reasonCell },
      { field: "status", headerName: "State", width: 165, cellRenderer: (p) => pill(stateName(p.value), p.value === "UNDER_REVIEW" ? "p-ok" : "") },
      { headerName: "Evidence", flex: 1, minWidth: 150, valueGetter: (p) => verdict(p.data) }, { headerName: "Actions", width: 190, sortable: false, filter: false, cellRenderer: cell(disputeActions) }],
  };
  // phone: one stacked column, plus the row's button where there is one
  const PHONE = {
    orders: [{ headerName: "Order", flex: 1, minWidth: 190, autoHeight: true, cellRenderer: cell((r) => [stack(el("span", "mono", r.id), el("span", "muted small", r.payer_email + " · $" + r.amount), chainPill(r.chain))]) }],
    ledger: [{ headerName: "Event", flex: 1, minWidth: 190, autoHeight: true, cellRenderer: cell((r) => [stack(el("b", "", EVENTS[r.event] || r.event), el("span", "mono muted small", "#" + r.id + " · " + r.when), chainPill(r.chain))]) }],
    help: [{ headerName: "Chat", flex: 1, minWidth: 190, autoHeight: true, cellRenderer: cell((r) => { const box = stack(el("span", "msgtxt", r.message), el("span", "muted small", (INTENTS[r.intent] || r.intent) + " · " + pretty(r.outcome)), demoPill(r.source));
      if (["pending", "failed"].includes(r.refund_status)) box.append(actButton("Approve refund", "/seller/refund/" + r.refund_id + "/approve", "Approve this refund? It is paid through PayPal (sandbox)."));
      return [box]; }) }],
    disputes: [{ headerName: "Dispute", flex: 1, minWidth: 170, autoHeight: true, cellRenderer: cell((r) => [stack(el("span", "mono", r.id), sourcePill(r.source), el("span", "small", pretty(r.reason) + " · $" + r.amount),
      el("span", "muted small", stateName(r.status) + (r.has_pack ? " · " + verdict(r) : "")))]) }, { headerName: "Actions", width: 150, autoHeight: true, cellRenderer: cell((r) => { const b = el("div", "stack gap"); b.append(...disputeActions(r)); return [b]; }) }],
  };
  const EMPTY = { orders: 'No orders yet. <a href="/">Open the store</a> and buy the guide to see one.', ledger: "No delivery events yet. The first purchase starts the chain.",
    help: "No support chats yet. Buyers' questions and the assistant's answers land here.", disputes: "No disputes yet. Use “Sync disputes” to pull one from PayPal, or load a sample." };
  const NO_ROWS = (name) => '<div class="empty"><svg class="ico" viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1"/></svg><p>' + EMPTY[name] + "</p></div>";

  function track(name) {
    const ids = new Set(data[name].map((r) => String(r.id)));
    fresh[name] = new Set([...ids].filter((i) => seen[name] && !seen[name].has(i)));
    seen[name] = ids;
  }

  function make(name) {
    if (grids[name]) return;
    track(name);
    fresh[name] = new Set();
    grids[name] = agGrid.createGrid($("grid-" + name), {
      columnDefs: phone ? PHONE[name] : DEFS[name], rowData: data[name], domLayout: data[name].length <= 12 ? "autoHeight" : "normal", rowHeight: phone || name === "help" ? undefined : name === "disputes" || name === "orders" ? 64 : 52, headerHeight: 46,
      animateRows: true, tooltipShowDelay: 400, defaultColDef: { sortable: !phone, filter: !phone, resizable: !phone, suppressHeaderMenuButton: true },
      getRowId: (p) => String(p.data.id), getRowClass: (p) => (fresh[name] && fresh[name].has(String(p.data.id)) ? "enter" : ""), overlayNoRowsTemplate: NO_ROWS(name),
      onRowClicked: name === "disputes" ? (e) => openDrawer(e.data.id) : undefined,
    });
  }

  function refresh() {
    Object.keys(grids).forEach((name) => { track(name); grids[name].setGridOption("rowData", data[name]); });
  }

  return { make, refresh, filter: (n, text) => grids[n] && grids[n].setGridOption("quickFilterText", text), csv: (n) => grids[n] && grids[n].exportDataAsCsv({ fileName: "accessproof-" + n + ".csv" }) };
})();
