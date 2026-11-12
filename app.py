import base64
import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import time

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request, send_file, session
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

import assistant  # noqa: E402
import db  # noqa: E402
import ledger  # noqa: E402
import limits  # noqa: E402
import paypal  # noqa: E402

PRODUCT = {"id": "notion-kit", "title": "Notion Freelancer Starter Kit", "price": "29.00",
           "file": os.path.join(os.path.dirname(os.path.abspath(__file__)), "products", "notion-freelancer-starter-kit.pdf"),
           "sample": os.path.join(os.path.dirname(os.path.abspath(__file__)), "products", "notion-freelancer-starter-kit-sample.pdf")}
TOKEN_DAYS = 7
ID_RE = re.compile(r"[A-Za-z0-9-]{1,64}")
CONTROL = re.compile("[\x00-\x08\x0b-\x1f\u202a-\u202e\u2066-\u2069]")  # control and bidi override characters

app = Flask(__name__)
if len(os.environ.get("APP_SECRET", "")) < 16:
    raise SystemExit("Set APP_SECRET in .env (a random string of at least 16 characters)")
app.secret_key = os.environ["APP_SECRET"]
app.config.update(MAX_CONTENT_LENGTH=256 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=bool(os.environ.get("PRODUCTION")))
log = logging.getLogger("accessproof")
if os.environ.get("PRODUCTION"):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
db.init()
app.jinja_env.filters["utc"] = ledger.fmt_ts
app.jinja_env.filters["eventname"] = lambda e: ledger.EVENT_LABELS.get(e, e)


@app.after_request
def headers(resp):
    resp.headers.update({"X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin",
                        "Permissions-Policy": "camera=(), microphone=(), geolocation=()"})
    if os.environ.get("PRODUCTION"):
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.path.startswith(("/dashboard", "/api/data", "/seller")):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(413)
def client_error(e):
    if request.path.startswith("/seller/"):  # the dashboard script expects JSON from these routes
        return jsonify(ok=False, message="Not found" if e.code in (404, 405) else "Request refused"), e.code
    texts = {404: ("Page not found", "That page does not exist or the link is wrong."), 405: ("Not allowed", "This page does not accept that action."),
             413: ("Too large", "That request was too large."), 400: ("Request refused", "The request could not be processed.")}
    return render_template("message.html", title=texts[e.code][0], text=texts[e.code][1]), e.code


@app.errorhandler(500)
def server_error(e):
    return render_template("message.html", title="Something went wrong", text="Please try again in a moment."), 500


def client_ip():
    # Behind Render the proxy is trusted for one hop (ProxyFix above); otherwise remote_addr is the peer.
    return request.remote_addr or ""


def sign(order_id, days=TOKEN_DAYS, now=None):
    payload = base64.urlsafe_b64encode(("%s|%d" % (order_id, (now or time.time()) + days * 86400)).encode()).decode()
    mac = hmac.new(os.environ["APP_SECRET"].encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + "." + mac


def check(token, now=None):
    """Returns the order id for a valid, unexpired token, else None."""
    try:
        payload, mac = token.split(".")
        want = hmac.new(os.environ["APP_SECRET"].encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, want):
            return None
        order_id, exp = base64.urlsafe_b64decode(payload.encode()).decode().rsplit("|", 1)
        return order_id if math.isfinite(float(exp)) and float(exp) > (now or time.time()) else None
    except (ValueError, TypeError):
        return None


def log_event(order_id, event, detail=None):
    return ledger.add(order_id, event, client_ip(), request.headers.get("User-Agent", "")[:300], detail)


@app.get("/")
def store():
    return render_template("store.html", product=PRODUCT)


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/config")
def config():
    return jsonify(client_id=os.environ["PAYPAL_CLIENT_ID"])


@app.post("/api/orders")
def create_order():
    if limits.rate_limited("order:" + limits.net(client_ip()), 30):
        return jsonify(error="Too many requests"), 429
    try:
        o = paypal.create_order(PRODUCT["price"], PRODUCT["title"], PRODUCT["id"])
        session["orders"] = (session.get("orders", []) + [o["id"]])[-5:]  # only the browser that started this checkout may complete it
        return jsonify(id=o["id"])
    except (paypal.PayPalError, KeyError):
        log.exception("create order failed")
        return jsonify(error="Could not start checkout"), 502


@app.post("/api/demo-order")
def demo_order():
    """A judge's shortcut: a demo order with a payment and a link already on record, so the assistant can be tried without paying. It never touches PayPal."""
    if limits.rate_limited("demo:" + limits.net(client_ip()), 8) or limits.rate_limited("demo:all", 150, 3600):
        return jsonify(error="Too many demo orders. Try again later."), 429
    oid = "DEMO-" + secrets.token_hex(6).upper()
    db.run("INSERT INTO orders(id,capture_id,payer_email,amount,currency,product,created_at,source) VALUES(?,?,?,?,?,?,datetime('now'),'demo')",
           (oid, "", "demo@example.invalid", PRODUCT["price"], "USD", PRODUCT["id"]))
    log_event(oid, "PURCHASE_CAPTURED", {"demo": True, "note": "demo order, no payment taken"})
    log_event(oid, "DELIVERY_EMAIL_LOGGED", {"to": "demo@example.invalid", "note": "download link issued; no email service is connected"})
    return jsonify(ok=True, redirect="/success/%s?t=%s" % (oid, sign(oid)))


@app.post("/api/orders/<order_id>/capture")
def capture(order_id):
    if not ID_RE.fullmatch(order_id):
        abort(404)
    if order_id not in session.get("orders", []):
        abort(403)
    if limits.rate_limited("order:" + limits.net(client_ip()), 30):
        return jsonify(error="Too many requests"), 429
    try:
        try:
            o = paypal.capture_order(order_id)
        except paypal.PayPalError as e:
            if e.status != 422 or "ORDER_ALREADY_CAPTURED" not in str(e.body):
                raise
            o = paypal.get_order(order_id)  # double click or retry: the buyer already paid
        unit = o["purchase_units"][0]
        cap = unit["payments"]["captures"][0]
        if cap["status"] != "COMPLETED":
            raise ValueError("capture status " + cap["status"])
        if (unit.get("reference_id"), cap["amount"]["value"], cap["amount"]["currency_code"]) != (PRODUCT["id"], PRODUCT["price"], "USD"):
            log.warning("capture %s does not match the product", order_id)
            return jsonify(error="This payment does not match the product"), 400
    except (paypal.PayPalError, KeyError, ValueError, IndexError, TypeError):
        log.exception("capture failed")
        return jsonify(error="Payment could not be completed"), 502
    email = o.get("payer", {}).get("email_address") or o.get("payment_source", {}).get("paypal", {}).get("email_address", "")
    new = db.changed("INSERT OR IGNORE INTO orders(id,capture_id,payer_email,amount,currency,product,created_at) VALUES(?,?,?,?,?,?,datetime('now'))",
                     (order_id, cap["id"], email, cap["amount"]["value"], cap["amount"]["currency_code"], PRODUCT["id"]))
    if new:  # only the request that inserted the order logs the purchase, so a double capture cannot repeat it
        log_event(order_id, "PURCHASE_CAPTURED", {"capture_id": cap["id"], "amount": cap["amount"]["value"]})
    return jsonify(ok=True, redirect="/success/%s?t=%s" % (order_id, sign(order_id)))


def buyer_order(order_id):
    """A real order inside the link lifetime, reached with its signed token (?t=); seed rows, sample rows and guessed ids have no buyer pages."""
    order = db.one("SELECT * FROM orders WHERE id=? AND source IN ('real','demo') AND created_at > datetime('now', ?)", (order_id, "-%d day" % TOKEN_DAYS))
    if not order or check(request.values.get("t", "")) != order_id:
        abort(404)
    return order


@app.get("/success/<order_id>")
def success(order_id):
    order = buyer_order(order_id)
    if not any(r["event"] == "DELIVERY_EMAIL_LOGGED" for r in ledger.rows(order_id)):
        log_event(order_id, "DELIVERY_EMAIL_LOGGED", {"to": order["payer_email"], "note": "download link issued; no email service is connected"})
    rows = ledger.rows(order_id)
    return render_template("success.html", order=order, product=PRODUCT, token=sign(order_id), link="/d/" + sign(order_id),
                           chain=ledger.blocks(rows), next_label=ledger.next_label(rows))


@app.get("/d/<token>")
def download(token):
    order_id = check(token)
    order = db.one("SELECT id, source FROM orders WHERE id=? AND source IN ('real','demo') AND created_at > datetime('now', ?)", (order_id, "-%d day" % TOKEN_DAYS)) if order_id else None
    if not order or db.one("SELECT id FROM ledger WHERE order_id=? AND event='REFUND_APPROVED'", (order_id,)):
        return render_template("message.html", title="Link not valid",
                               text="This download link is invalid, has expired, or the order was refunded."), 403
    demo = order["source"] == "demo"  # a demo order gets the free sample; the full guide is only for paid orders
    path, name = (PRODUCT["sample"], "notion-freelancer-starter-kit-SAMPLE.pdf") if demo else (PRODUCT["file"], "notion-freelancer-starter-kit.pdf")
    if request.method == "GET" and os.path.exists(path):  # link scanners send HEAD
        log_event(order_id, "LINK_OPENED")
        log_event(order_id, "FILE_DOWNLOADED")
    return send_file(path, as_attachment=True, download_name=name)


def chat_view(row, rows_by_id):
    """One stored help request as a chat turn (no IPs, only public event fields)."""
    cited = [rows_by_id[i] for i in json.loads(row["cited"] or "[]") if i in rows_by_id]
    return dict(row, events=ledger.public_events(cited))


@app.route("/order/<order_id>/help", methods=["GET", "POST"])
def help_page(order_id):
    order = buyer_order(order_id)
    wants_json = request.is_json
    if request.method == "POST":
        if limits.rate_limited("help:" + limits.net(client_ip()), 30):  # a real conversation needs room; the model quota is the real limit
            if wants_json:
                return jsonify(error="Too many requests. Try again later."), 429
            return render_template("message.html", title="Slow down", text="Too many requests. Try again later."), 429
        try:
            body = (request.get_json(silent=True) or {}) if wants_json else {}
        except RecursionError:  # absurdly nested JSON
            return jsonify(error="That request could not be read."), 400
        raw = body.get("message", "") if wants_json else request.form.get("message", "")
        message = CONTROL.sub("", str(raw)).strip()[:1000]
        if wants_json and not message:
            return jsonify(error="Please type a message."), 400
        if message:
            result = assistant.handle_help(order, message, sign(order_id))
            if result["action"] == "RESEND":
                log_event(order_id, "LINK_RESENT")
            if wants_json:
                body = {k: result[k] for k in ("id", "reply", "intent", "action", "flagged", "fallback", "outcome", "refund", "link", "follow_ups")}
                return jsonify(dict(body, events=ledger.public_events(result["events"])))
    rows = ledger.rows(order_id)
    by_id = {r["id"]: r for r in rows}
    history = [chat_view(h, by_id) for h in db.query("SELECT * FROM help_requests WHERE order_id=? ORDER BY id", (order_id,))]
    return render_template("help.html", order=order, history=history, token=sign(order_id), status=ledger.status_line(rows), chain=ledger.blocks(rows))


@app.post("/order/<order_id>/help/<int:help_id>/solved")
def solved(order_id, help_id):
    if check(request.form.get("token", "")) != order_id:  # same signed token as the download link
        return render_template("message.html", title="Not allowed", text="This confirmation link is not valid."), 403
    done = db.changed("UPDATE help_requests SET outcome='deflected' WHERE id=? AND order_id=? AND outcome IN ('open','resent')",
                      (help_id, order_id))
    if not done:
        return render_template("message.html", title="Already noted", text="This request was already closed."), 409
    return render_template("message.html", title="Thanks", text="We noted that your question was answered.")


import seller  # noqa: E402

app.register_blueprint(seller.bp)
