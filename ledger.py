import hashlib
import json
from datetime import datetime, timezone

import db

EVENT_LABELS = {"PURCHASE_CAPTURED": "Payment captured", "DELIVERY_EMAIL_LOGGED": "Download link issued", "LINK_OPENED": "Link opened",
                "FILE_DOWNLOADED": "File downloaded", "LINK_RESENT": "New link issued", "REFUND_APPROVED": "Refund approved", "EVIDENCE_SUBMITTED": "Evidence submitted"}
ZERO = "0" * 64


def canon(order_id, event, ts, ip, ua, detail):
    return json.dumps({"order_id": order_id, "event": event, "ts": ts, "ip": ip, "ua": ua, "detail": detail},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def make_hash(prev, row):
    return hashlib.sha256((prev + canon(row["order_id"], row["event"], row["ts"], row["ip"], row["ua"],
                                         row["detail"])).encode()).hexdigest()


def add(order_id, event, ip="", ua="", detail=None, ts=None):
    """Append an event. Uses one connection with an immediate lock so the chain stays linear."""
    ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    detail = json.dumps(detail or {}, sort_keys=True)
    con = db.connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        last = con.execute("SELECT hash FROM ledger WHERE order_id=? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
        prev = last["hash"] if last else ZERO
        row = {"order_id": order_id, "event": event, "ts": ts, "ip": ip, "ua": ua, "detail": detail}
        cur = con.execute("INSERT INTO ledger(order_id,event,ts,ip,ua,detail,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?)",
                          (order_id, event, ts, ip, ua, detail, prev, make_hash(prev, row)))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def fmt_ts(ts):
    """'2026-11-11T15:42:09+00:00' -> '11 Nov 2026, 15:42 UTC' (all stored times are UTC)."""
    try:
        d = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return str(ts)
    return "%d %s" % (d.day, d.strftime("%b %Y, %H:%M UTC"))


SHORT = {"PURCHASE_CAPTURED": "Paid", "DELIVERY_EMAIL_LOGGED": "Link issued", "LINK_OPENED": "Opened", "FILE_DOWNLOADED": "Downloaded",
         "LINK_RESENT": "Re-sent", "REFUND_APPROVED": "Refunded", "EVIDENCE_SUBMITTED": "Evidence sent"}
FLOW = ["PURCHASE_CAPTURED", "DELIVERY_EMAIL_LOGGED", "LINK_OPENED", "FILE_DOWNLOADED"]


def blocks(rows, limit=4):
    """Events as numbered proof-chain blocks (no IP or user agent)."""
    return [{"id": r["id"], "label": SHORT.get(r["event"], r["event"]), "when": fmt_ts(r["ts"]), "short": short_ts(r["ts"]), "hash": (r["hash"] or "")[:8]} for r in rows[:limit]]


def short_ts(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%H:%M")
    except (TypeError, ValueError):
        return ""


def next_label(rows):
    seen = {r["event"] for r in rows}
    return next((SHORT[e] for e in FLOW if e not in seen), None)


def public_events(rows):
    return [{"id": r["id"], "name": EVENT_LABELS.get(r["event"], r["event"]), "when": fmt_ts(r["ts"])} for r in rows]


def status_line(rows):
    events = {r["event"]: r for r in rows}
    if "FILE_DOWNLOADED" in events:
        return "Your payment was captured and your file was downloaded on %s." % fmt_ts(events["FILE_DOWNLOADED"]["ts"])
    if "DELIVERY_EMAIL_LOGGED" in events:
        return "Your payment was captured and your download link was issued on %s. I don't see it opened yet." % fmt_ts(events["DELIVERY_EMAIL_LOGGED"]["ts"])
    return "Your payment was captured."


def rows(order_id):
    return db.query("SELECT * FROM ledger WHERE order_id=? ORDER BY id", (order_id,))


def head(order_id):
    """The hash of the newest row: whoever holds a copy can later tell if the chain was rebuilt."""
    return (rows(order_id) or [{"hash": ZERO}])[-1]["hash"]


def first_broken(order_id):
    """Position (0 = first step) of the first row that does not match the one before it, else None."""
    prev = ZERO
    for i, r in enumerate(rows(order_id)):
        if r["prev_hash"] != prev or r["hash"] != make_hash(prev, r):
            return i
        prev = r["hash"]
    return None


def verify(order_id):
    return "ok" if first_broken(order_id) is None else "broken"
