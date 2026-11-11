import hmac
import json
import logging
import os
import secrets
import time
from functools import wraps

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session

import assistant
import db
import evidence
import ledger
import limits
import overview
import paypal
from disputes import has_link, make_sample, raw_of, refresh, requested_type, upsert_dispute

bp = Blueprint("seller", __name__)
log = logging.getLogger("accessproof")
SESSION_SECONDS = 8 * 3600
FEE = 15  # est. US standard dispute fee, USD


def login_required(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if not session.get("seller") or time.time() - session.get("t", 0) > SESSION_SECONDS:
            return (jsonify(error="Please log in"), 401) if request.method != "GET" else redirect("/login")
        if request.method == "POST":
            sent = request.headers.get("X-CSRF") or request.form.get("csrf", "")
            if not hmac.compare_digest(sent.encode(), session.get("csrf", "").encode()):
                abort(400)
        return view(*a, **kw)
    return wrapper


def reply(ok, message, code=200):
    return jsonify(ok=ok, message=message), code


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    key = "login:" + (request.remote_addr or "")
    if request.method == "POST":
        if limits.count(key) >= 5:  # failed attempts only
            return render_template("login.html", error="Too many attempts. Try again later."), 429
        wanted = os.environ.get("SELLER_PASSWORD", "")
        if wanted and hmac.compare_digest(request.form.get("password", "").encode(), wanted.encode()):
            session.clear()
            session.update(seller=True, csrf=secrets.token_hex(16), t=time.time())
            return redirect("/dashboard")
        limits.add(key)
        error = "Wrong password"
    return render_template("login.html", error=error)


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/login")


@bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", csrf=session["csrf"])


@bp.get("/api/data")
@login_required
def data():
    orders = db.query("SELECT * FROM orders ORDER BY created_at DESC")
    chain = {o["id"]: ledger.verify(o["id"]) for o in orders}
    rows = db.query("SELECT * FROM ledger ORDER BY id DESC")
    disputes = db.query("SELECT * FROM disputes ORDER BY (source='paypal') DESC, created_at DESC")
    cache = {}
    for d in disputes:
        raw = raw_of(d)
        d.update(overview.dispute_view(d, cache))
        d.pop("raw")
        pack = json.loads(d.pop("pack") or "null")
        d.update(has_pack=bool(pack), summary=pack and pack["summary"],
                 can_submit=d["source"] == "paypal" and has_link(raw, "provide_evidence") and bool(pack),
                 can_adjudicate=d["status"] == "UNDER_REVIEW" and has_link(raw, "adjudicate"),
                 can_offer=d["stage"] == "INQUIRY" and d["source"] == "paypal" and d["status"] == "WAITING_FOR_SELLER_RESPONSE")
    # demo rows (source=seed) are left out so the cards only show real and sample activity
    stats = {"deflected": db.one("SELECT COUNT(*) n FROM help_requests WHERE outcome='deflected' AND source!='seed'")["n"],
             "filed": db.one("SELECT COUNT(*) n FROM disputes WHERE last_result LIKE 'Evidence submitted%' AND source!='seed'")["n"]}
    stats["fees"] = stats["deflected"] * FEE
    stats["refunds"] = db.one("SELECT COUNT(*) n FROM ledger l JOIN orders o ON o.id=l.order_id WHERE l.event='REFUND_APPROVED' AND o.source!='seed'")["n"]
    return jsonify(stats=stats, orders=[dict(o, chain=chain[o["id"]], when=ledger.fmt_ts(o["created_at"])) for o in orders],
                   ledger=[dict(r, chain=chain.get(r["order_id"], ""), when=ledger.fmt_ts(r["ts"])) for r in rows],
                   help=db.query("SELECT h.*, r.id refund_id, r.status refund_status FROM help_requests h "
                                 "LEFT JOIN refund_requests r ON r.help_id=h.id ORDER BY h.id DESC"),
                   disputes=disputes, feed=overview.feed(), timeline=overview.timeline())


@bp.post("/seller/refund/<int:rid>/approve")
@login_required
def approve_refund(rid):
    rr = db.one("SELECT r.*, o.capture_id, o.source FROM refund_requests r JOIN orders o ON o.id=r.order_id WHERE r.id=?", (rid,))
    if not rr or rr["status"] not in ("pending", "failed"):
        return reply(False, "Refund request not found or already handled", 404)
    if rr["source"] != "real":
        return reply(False, "Demo order: it has no real PayPal capture", 400)
    try:
        res = paypal.refund(rr["capture_id"], rr["amount"], "Goodwill refund approved by the seller", "refund-%d" % rid)
    except paypal.PayPalError:
        log.exception("refund failed")
        db.run("UPDATE refund_requests SET status='failed' WHERE id=?", (rid,))
        return reply(False, "PayPal did not accept the refund", 502)
    db.run("UPDATE refund_requests SET status='approved', paypal_refund_id=? WHERE id=?", (res.get("id"), rid))
    db.run("UPDATE help_requests SET outcome='refunded' WHERE id=?", (rr["help_id"],))
    ledger.add(rr["order_id"], "REFUND_APPROVED", "seller", "seller dashboard", detail={"refund_id": res.get("id"), "status": res.get("status")})
    return reply(True, "Refund %s: %s" % (res.get("id"), res.get("status")))


@bp.post("/seller/disputes/sync")
@login_required
def sync():
    try:
        items = paypal.list_disputes()
        for it in items:
            upsert_dispute(paypal.get_dispute(it["dispute_id"]))
    except (paypal.PayPalError, KeyError):
        log.exception("dispute sync failed")
        return reply(False, "Could not reach PayPal disputes", 502)
    return reply(True, "Synced %d dispute(s) from PayPal" % len(items))


@bp.post("/seller/disputes/sample")
@login_required
def sample():
    order = db.one("SELECT * FROM orders ORDER BY (source='real') DESC, created_at DESC LIMIT 1")
    if not order:
        return reply(False, "No order to attach a sample dispute to", 400)
    make_sample(order, request.values.get("reason") == "snad")
    return reply(True, "Sample dispute added (not from PayPal)")


def load(dispute_id):
    d = db.one("SELECT * FROM disputes WHERE id=?", (dispute_id,))
    if not d or not d["order_id"]:
        abort(404)
    return d, db.one("SELECT * FROM orders WHERE id=?", (d["order_id"],))


def pdf_for(d, order):
    return evidence.build_pdf(d, order, ledger.rows(order["id"]), json.loads(d["pack"]), ledger.verify(order["id"]))


@bp.post("/seller/disputes/<dispute_id>/pack")
@login_required
def pack(dispute_id):
    d, order = load(dispute_id)
    if d["pack"]:
        return reply(True, "Evidence pack already built")
    res = assistant.evidence_pack(d, ledger.rows(order["id"]))
    if res.get("unavailable"):
        return reply(False, "AI draft unavailable, try again shortly", 503)
    db.run("UPDATE disputes SET pack=?, covered=?, recommendation=? WHERE id=?",
           (json.dumps(res), int(res["covered"]), res["recommendation"], dispute_id))
    return reply(True, "Evidence pack built: %s" % res["recommendation"])


@bp.get("/seller/disputes/<dispute_id>/pdf")
@login_required
def pdf(dispute_id):
    d, order = load(dispute_id)
    if not d["pack"]:
        abort(404)
    return Response(pdf_for(d, order), mimetype="application/pdf", headers={"Content-Disposition": "inline; filename=evidence.pdf"})


@bp.post("/seller/disputes/<dispute_id>/submit")
@login_required
def submit(dispute_id):
    d, order = load(dispute_id)
    if d["source"] != "paypal":
        return reply(False, "Sample dispute: it does not exist at PayPal, so evidence cannot be submitted", 400)
    if not d["pack"]:
        return reply(False, "Build the evidence pack first", 400)
    if not has_link(raw_of(d), "provide_evidence"):
        return reply(False, "PayPal does not accept evidence for this dispute right now", 400)
    try:
        paypal.provide_evidence(dispute_id, pdf_for(d, order), json.loads(d["pack"])["summary"], requested_type(raw_of(d)))
    except paypal.PayPalError as e:
        log.exception("provide-evidence failed")
        db.run("UPDATE disputes SET last_result=? WHERE id=?", ("Submit failed: PayPal %s" % e.status, dispute_id))
        return reply(False, "PayPal rejected the evidence (status %s)" % e.status, 502)
    ledger.add(order["id"], "EVIDENCE_SUBMITTED", "seller", "seller dashboard", detail={"dispute_id": dispute_id})
    refresh(dispute_id)
    db.run("UPDATE disputes SET last_result='Evidence submitted to PayPal' WHERE id=?", (dispute_id,))
    return reply(True, "Evidence submitted to PayPal")


@bp.post("/seller/disputes/<dispute_id>/offer")
@login_required
def offer(dispute_id):
    d, order = load(dispute_id)
    if d["source"] != "paypal":
        return reply(False, "Sample dispute: it does not exist at PayPal", 400)
    if d["stage"] != "INQUIRY":
        return reply(False, "Offers are only possible in the INQUIRY stage", 400)
    try:
        paypal.make_offer(dispute_id, d["amount"], "Refund offered to resolve this dispute")
    except paypal.PayPalError as e:
        log.exception("make-offer failed")
        return reply(False, "PayPal rejected the offer (status %s)" % e.status, 502)
    refresh(dispute_id)
    db.run("UPDATE disputes SET last_result='Refund offer sent' WHERE id=?", (dispute_id,))
    return reply(True, "Refund offer sent")


@bp.post("/seller/disputes/<dispute_id>/adjudicate")
@login_required
def adjudicate(dispute_id):
    d, _ = load(dispute_id)
    if d["source"] != "paypal" or not has_link(raw_of(d), "adjudicate"):
        return reply(False, "PayPal does not allow a sandbox decision for this dispute", 400)
    try:
        paypal.adjudicate(dispute_id, "SELLER_FAVOR")
    except paypal.PayPalError as e:
        log.exception("adjudicate failed")
        return reply(False, "Sandbox decision failed (status %s)" % e.status, 502)
    refresh(dispute_id)
    db.run("UPDATE disputes SET last_result='Sandbox decision: seller favor' WHERE id=?", (dispute_id,))
    return reply(True, "Sandbox decision: seller favor")


@bp.post("/webhooks/paypal")
def webhook():
    needed = ("paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id", "paypal-transmission-sig", "paypal-transmission-time")
    if any(not request.headers.get(h) for h in needed) or limits.rate_limited("webhook:" + (request.remote_addr or ""), 60):
        return "invalid request", 400  # no call to PayPal for requests that cannot be real webhooks
    try:
        event = request.get_json(silent=True)
    except RecursionError:
        event = None
    if not isinstance(event, dict) or not paypal.verify_webhook(request.headers, event):
        return "invalid signature", 400
    if event.get("event_type") in ("CUSTOMER.DISPUTE.CREATED", "CUSTOMER.DISPUTE.UPDATED"):
        try:
            upsert_dispute(paypal.get_dispute(event["resource"]["dispute_id"]))
        except (paypal.PayPalError, KeyError, TypeError):
            log.exception("webhook dispute sync failed")
            return "error", 500
    return "ok", 200
