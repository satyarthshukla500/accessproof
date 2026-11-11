/* AG Grid tables for the seller dashboard (helpers come from dashboard.js) */
const Grids = (() => {
  const grids = {};
  const seen = {};
  const fresh = {};
  const EVENTS = { PURCHASE_CAPTURED: "Payment captured", DELIVERY_EMAIL_LOGGED: "Download link issued", LINK_OPENED: "Link opened", FILE_DOWNLOADED: "File downloaded",
    LINK_RESENT: "New link issued", REFUND_APPROVED: "Refund approved", EVIDENCE_SUBMITTED: "Evidence submitted" };
  const INTENTS = { NOT_RECEIVED: "Not received", CANT_OPEN: "Can't open", WANTS_REFUND: "Wants refund", NOT_AS_DESCRIBED: "Not as described", OTHER: "Other" };
  const ACTIONS = { RESEND: "Re-sent link", OFFER_REFUND: "Refund suggested", NONE: "None" };
  const OUTCOMES = { deflected: "p-ok", refunded: "p-ok", resent: "", refund_pending: "p-warn", escalated: "p-warn", open: "" };

  const pill = (text, cls) => el("span", "pill sm plain " + (cls || ""), text);
  const cell = (build) => (p) => { const box = el("span", "cellbtn"); build(p.data).forEach((n) => box.append(n)); return box; };
  const shortSource = (s) => (s === "paypal" ? pill("Real", "p-real") : s === "sample" ? pill("Sample", "p-sample") : s === "seed" ? pill("Seed", "p-seed") : "");
  const sourcePill = (s) => (s === "paypal" ? pill("Real · PayPal sandbox", "p-real") : s === "sample" ? pill("Sample (not from PayPal)", "p-sample") : s === "seed" ? pill("Seed", "p-seed") : "");
  const dash = (p) => p.value || "—";
  const source = { field: "source", headerName: "Source", width: 100, cellRenderer: (p) => shortSource(p.value) };
  const chain = { field: "chain", headerName: "Chain", width: 110, cellRenderer: (p) => pill(p.value === "ok" ? "Verified" : "Broken", p.value === "ok" ? "p-ok" : "p-warn") };

  function disputeCell(r) {
    const box = el("div", "stack");
    box.append(el("span", "mono", r.id), sourcePill(r.source));
    return [box];
  }

  function disputeActions(r) {
    const u = "/seller/disputes/" + encodeURIComponent(r.id);
    const out = [];
    if (!r.has_pack) out.push(actButton("Build evidence pack", u + "/pack"));
    else { const a = el("a", "btn sm ghost", "View PDF"); a.href = u + "/pdf"; a.target = "_blank"; a.rel = "noopener"; a.addEventListener("click", (e) => e.stopPropagation()); out.push(a); }
    if (r.can_submit) out.push(actButton("Submit evidence", u + "/submit", "Submit this evidence pack to PayPal?"));
    if (r.can_offer) out.push(actButton("Make offer", u + "/offer", "Offer the buyer a full refund of $" + r.amount + "?", "ghost"));
    if (r.can_adjudicate) out.push(actButton("Simulate decision", u + "/adjudicate", "", "ghost"));
    return out;
  }

  const EMPTY = { orders: "No orders yet. Buy the product in the store to see one.", ledger: "No delivery events yet.", help: "No support chats yet.", disputes: "No disputes yet. Sync from PayPal or load a sample." };
  const DEFS = {
    orders: [{ field: "id", headerName: "Order", width: 190, cellClass: "mono" }, { field: "payer_email", headerName: "Payer", flex: 1, minWidth: 170 },
      { field: "amount", headerName: "Amount", width: 100, valueFormatter: (p) => "$" + p.value }, { field: "when", headerName: "Created", width: 190 }, chain, source],
    ledger: [{ field: "id", headerName: "ID", width: 80, cellClass: "mono", valueFormatter: (p) => "#" + p.value }, { field: "when", headerName: "Time", width: 190 },
      { field: "event", headerName: "Event", width: 190, valueFormatter: (p) => EVENTS[p.value] || p.value }, { field: "order_id", headerName: "Order", width: 170, cellClass: "mono" },
      { field: "ip", headerName: "IP", width: 100, valueFormatter: dash }, { field: "ua", headerName: "User agent", flex: 1, minWidth: 90, valueFormatter: dash }, chain],
    help: [{ field: "id", headerName: "ID", width: 70 }, { field: "message", headerName: "Buyer message", flex: 1, minWidth: 130, tooltipField: "message" },
      { field: "intent", headerName: "Intent", width: 140, valueFormatter: (p) => INTENTS[p.value] || p.value }, { field: "action", headerName: "Action", width: 150, valueFormatter: (p) => ACTIONS[p.value] || p.value },
      { field: "outcome", headerName: "Outcome", width: 130, cellRenderer: (p) => pill(pretty(p.value), OUTCOMES[p.value]) },
      { field: "flagged", headerName: "Flagged", width: 100, cellRenderer: (p) => (p.value ? pill("Flagged", "p-warn") : "") },
      { headerName: "Refund", width: 170, cellRenderer: cell((r) => (["pending", "failed"].includes(r.refund_status)
        ? [actButton("Approve refund", "/seller/refund/" + r.refund_id + "/approve", "Approve this refund? It is paid through PayPal (sandbox).")] : [el("span", "muted", r.refund_status || "")])) }, source],
    disputes: [{ headerName: "Dispute", width: 210, cellRenderer: cell(disputeCell) },
      { headerName: "Reason", width: 150, valueGetter: (p) => pretty(p.data.reason) + " · $" + p.data.amount },
      { field: "status", headerName: "State", width: 150, cellRenderer: (p) => pill(stateName(p.value), p.value === "UNDER_REVIEW" ? "p-ok" : "") },
      { headerName: "Evidence", width: 150, valueGetter: (p) => verdict(p.data) },
      { headerName: "Actions", width: 220, cellRenderer: cell(disputeActions) }, { field: "last_result", headerName: "Last result", minWidth: 90, flex: 1, valueFormatter: dash }],
  };
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
      columnDefs: DEFS[name], rowData: data[name], rowHeight: name === "disputes" ? 64 : 52, headerHeight: 46, animateRows: true, tooltipShowDelay: 400,
      defaultColDef: { sortable: true, filter: true, resizable: true }, getRowId: (p) => String(p.data.id),
      getRowClass: (p) => (fresh[name] && fresh[name].has(String(p.data.id)) ? "enter" : ""), overlayNoRowsTemplate: NO_ROWS(name),
      onRowClicked: name === "disputes" ? (e) => openDrawer(e.data.id) : undefined,
    });
  }

  function refresh() {
    Object.keys(grids).forEach((name) => { track(name); grids[name].setGridOption("rowData", data[name]); });
  }

  return { make, refresh };
})();
