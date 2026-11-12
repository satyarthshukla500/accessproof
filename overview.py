import json

import db
import ledger

FEED = {"REFUND_APPROVED": ("ok", "Refund completed"), "EVIDENCE_SUBMITTED": ("ok", "Evidence submitted to PayPal"),
        "FILE_DOWNLOADED": ("info", "File downloaded"), "PURCHASE_CAPTURED": ("info", "Payment captured")}


def key(ts):
    """Sort key that works for both ledger times (ISO with offset) and help times (naive UTC)."""
    return (ts or "")[:19].replace(" ", "T")


def feed(limit=8):
    """Latest activity, newest first: ledger events and help-chat outcomes. Seed rows are left out; demo rows carry a Demo tag (the totals never count them)."""
    items = [{"kind": FEED[r["event"]][0], "text": tag(r["source"], FEED[r["event"]][1]), "ts": r["ts"]} for r in db.query(
        "SELECT l.event, l.ts, o.source FROM ledger l JOIN orders o ON o.id=l.order_id WHERE o.source!='seed' AND l.event IN (%s) ORDER BY l.id DESC LIMIT ?"
        % ",".join("?" * len(FEED)), (*FEED, limit))]
    for h in db.query("SELECT flagged, outcome, created_at, source FROM help_requests WHERE source!='seed' AND (flagged=1 OR outcome='deflected') ORDER BY id DESC LIMIT ?", (limit,)):
        if h["outcome"] == "deflected":
            items.append({"kind": "ok", "text": tag(h["source"], "Chat resolved by the buyer"), "ts": h["created_at"]})
        if h["flagged"] and h["outcome"] == "escalated":
            items.append({"kind": "warn", "text": tag(h["source"], "Manipulation attempt flagged"), "ts": h["created_at"]})
    items.sort(key=lambda i: key(i["ts"]), reverse=True)
    return [dict(i, when=ledger.fmt_ts(i["ts"])) for i in items[:limit]]


def tag(source, text):
    return "Demo · " + text if source == "demo" else text


def timeline(limit=6):
    rows = db.query("SELECT l.id, l.event, l.ts, l.order_id, o.source FROM ledger l JOIN orders o ON o.id=l.order_id WHERE o.source!='seed' ORDER BY l.id DESC LIMIT ?", (limit,))
    return [{"id": r["id"], "name": tag(r["source"], ledger.EVENT_LABELS.get(r["event"], r["event"])), "when": ledger.fmt_ts(r["ts"]), "order": r["order_id"]} for r in rows]


def dispute_view(d, rows_by_order):
    """Pack claims with the ledger events they cite, for the dispute drawer."""
    pack = json.loads(d.get("pack") or "null")
    rows = rows_by_order.setdefault(d["order_id"], ledger.rows(d["order_id"])) if d["order_id"] else []
    events = {r["id"]: {"name": ledger.EVENT_LABELS.get(r["event"], r["event"]), "when": ledger.fmt_ts(r["ts"])} for r in rows}
    # what PayPal itself holds for the case (its evidence list from the last sync), so the seller can see the filing on PayPal's side
    record = [{"who": "Seller" if e.get("source") == "SUBMITTED_BY_SELLER" else "Buyer", "kind": (e.get("evidence_type") or "").replace("_", " ").capitalize(),
               "when": ledger.fmt_ts(e.get("date")), "pdf": bool(e.get("documents"))} for e in json.loads(d.get("raw") or "{}").get("evidences") or []]
    return {"claims": pack["claims"] if pack else [], "events": events, "chain": ledger.blocks(rows), "record": record,
            "filed": any(r["who"] == "Seller" for r in record)}
