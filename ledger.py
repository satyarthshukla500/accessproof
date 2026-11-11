import hashlib
import json
from datetime import datetime, timezone

import db

EVENT_LABELS = {"PURCHASE_CAPTURED": "Payment captured", "DELIVERY_EMAIL_LOGGED": "Download link issued", "LINK_OPENED": "Link opened",
                "FILE_DOWNLOADED": "File downloaded", "LINK_RESENT": "New link issued", "REFUND_APPROVED": "Refund approved"}
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


def rows(order_id):
    return db.query("SELECT * FROM ledger WHERE order_id=? ORDER BY id", (order_id,))


def verify(order_id):
    prev = ZERO
    for r in rows(order_id):
        if r["prev_hash"] != prev or r["hash"] != make_hash(prev, r):
            return "broken"
        prev = r["hash"]
    return "ok"
