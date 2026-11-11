import json
import logging

import db
import paypal

log = logging.getLogger("accessproof")


def has_link(raw, name):
    return any(k.get("rel", "").replace("-", "_") == name for k in raw.get("links", []))


def refresh(dispute_id):
    """Re-reads a dispute after a successful action; a failure here must not hide that the action worked."""
    try:
        upsert_dispute(paypal.get_dispute(dispute_id))
    except (paypal.PayPalError, KeyError):
        log.exception("dispute refresh failed")


def requested_type(raw):
    """PayPal says which evidence type it wants from the seller (source REQUESTED_FROM_SELLER); use that one."""
    for e in raw.get("evidences", []):
        if e.get("source") == "REQUESTED_FROM_SELLER" and e.get("evidence_type"):
            return e["evidence_type"]
    return "PROOF_FOR_SOFTWARE_OR_SERVICE_DELIVERED"


def raw_of(d):
    return json.loads(d["raw"] or "{}")


def upsert_dispute(raw, source="paypal"):
    tx = (raw.get("disputed_transactions") or [{}])[0].get("seller_transaction_id", "")
    order = db.one("SELECT id FROM orders WHERE capture_id=? OR id=?", (tx, tx))
    amount = raw.get("dispute_amount", {})
    vals = (order["id"] if order else None, tx, raw.get("reason"), raw.get("status"), raw.get("dispute_life_cycle_stage"),
            amount.get("value"), amount.get("currency_code"), json.dumps(raw), raw["dispute_id"])
    if db.one("SELECT id FROM disputes WHERE id=?", (raw["dispute_id"],)):
        db.run("UPDATE disputes SET order_id=?, capture_id=?, reason=?, status=?, stage=?, amount=?, currency=?, raw=? WHERE id=?", vals)
    else:
        db.run("INSERT INTO disputes(order_id,capture_id,reason,status,stage,amount,currency,raw,id,source,created_at) "
               "VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now'))", vals + (source,))


def make_sample(order, snad):
    """Adds a dispute shaped like PayPal's response for an existing order; it is marked sample and never sent to PayPal."""
    n = db.one("SELECT COUNT(*) n FROM disputes WHERE source='sample'")["n"] + 1
    upsert_dispute({
        "dispute_id": "SAMPLE-D-%04d" % n,
        "reason": "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED" if snad else "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
        "status": "WAITING_FOR_SELLER_RESPONSE", "dispute_life_cycle_stage": "INQUIRY",
        "dispute_amount": {"currency_code": order["currency"], "value": order["amount"]},
        "disputed_transactions": [{"seller_transaction_id": order["capture_id"]}], "links": []}, "sample")
