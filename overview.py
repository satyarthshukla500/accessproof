import json

import db
import ledger

FEED = {"REFUND_APPROVED": ("ok", "Refund completed"), "EVIDENCE_SUBMITTED": ("ok", "Evidence submitted to PayPal"),
        "FILE_DOWNLOADED": ("info", "File downloaded"), "PURCHASE_CAPTURED": ("info", "Payment captured")}


def key(ts):
    """Sort key that works for both ledger times (ISO with offset) and help times (naive UTC)."""
    return (ts or "")[:19].replace(" ", "T")


def feed(limit=8):
    """Latest real activity, newest first: ledger events and help-chat outcomes (seed rows left out)."""
    items = [{"kind": FEED[r["event"]][0], "text": FEED[r["event"]][1], "ts": r["ts"]} for r in db.query(
        "SELECT l.event, l.ts FROM ledger l JOIN orders o ON o.id=l.order_id WHERE o.source!='seed' AND l.event IN (%s) ORDER BY l.id DESC LIMIT ?"
        % ",".join("?" * len(FEED)), (*FEED, limit))]
    for h in db.query("SELECT flagged, outcome, created_at FROM help_requests WHERE source!='seed' AND (flagged=1 OR outcome='deflected') ORDER BY id DESC LIMIT ?", (limit,)):
        if h["outcome"] == "deflected":
            items.append({"kind": "ok", "text": "Chat resolved by the buyer", "ts": h["created_at"]})
        if h["flagged"] and h["outcome"] == "escalated":
            items.append({"kind": "warn", "text": "Manipulation attempt flagged", "ts": h["created_at"]})
    items.sort(key=lambda i: key(i["ts"]), reverse=True)
    return [dict(i, when=ledger.fmt_ts(i["ts"])) for i in items[:limit]]


def timeline(limit=6):
    rows = db.query("SELECT l.id, l.event, l.ts, l.order_id FROM ledger l JOIN orders o ON o.id=l.order_id WHERE o.source!='seed' ORDER BY l.id DESC LIMIT ?", (limit,))
    return [{"id": r["id"], "name": ledger.EVENT_LABELS.get(r["event"], r["event"]), "when": ledger.fmt_ts(r["ts"]), "order": r["order_id"]} for r in rows]


def dispute_view(d, rows_by_order):
    """Pack claims with the ledger events they cite, for the dispute drawer."""
    pack = json.loads(d.get("pack") or "null")
    rows = rows_by_order.setdefault(d["order_id"], ledger.rows(d["order_id"])) if d["order_id"] else []
    events = {r["id"]: {"name": ledger.EVENT_LABELS.get(r["event"], r["event"]), "when": ledger.fmt_ts(r["ts"])} for r in rows}
    return {"claims": pack["claims"] if pack else [], "events": events, "chain": ledger.blocks(rows)}
