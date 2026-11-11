import json
import os
import time

import requests

SANDBOX = "https://api-m.sandbox.paypal.com"
BASE = os.environ.get("PAYPAL_BASE", SANDBOX)
if BASE != SANDBOX:
    raise SystemExit("Refusing to start: only the PayPal sandbox is allowed")

_token = {"value": None, "exp": 0}


class PayPalError(Exception):
    def __init__(self, status, body):
        super().__init__("PayPal %s: %s" % (status, str(body)[:300]))
        self.status = status
        self.body = body


def token():
    if _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    try:
        r = requests.post(BASE + "/v1/oauth2/token", auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"]),
                          data={"grant_type": "client_credentials"}, timeout=20)
        j = r.json()
    except (requests.RequestException, ValueError) as e:
        raise PayPalError(0, "oauth request failed: %s" % type(e).__name__) from e
    if r.status_code != 200 or "access_token" not in j:
        raise PayPalError(r.status_code, "oauth failed")
    _token.update(value=j["access_token"], exp=time.time() + j.get("expires_in", 300))
    return _token["value"]


def call(method, path, **kw):
    headers = {"Authorization": "Bearer " + token()}
    headers.update(kw.pop("headers", {}))
    try:
        r = requests.request(method, BASE + path, headers=headers, timeout=20, **kw)
    except requests.RequestException as e:
        raise PayPalError(0, "request failed: %s" % type(e).__name__) from e
    try:
        body = r.json() if r.text else {}
    except ValueError:
        body = {"raw": r.text[:300]}
    if r.status_code >= 300:
        raise PayPalError(r.status_code, body)
    return body


def create_order(amount, description, reference_id):
    return call("POST", "/v2/checkout/orders", json={"intent": "CAPTURE", "purchase_units": [
        {"reference_id": reference_id, "description": description,
         "amount": {"currency_code": "USD", "value": amount}}]})


def get_order(order_id):
    return call("GET", "/v2/checkout/orders/" + order_id)


def capture_order(order_id):
    return call("POST", "/v2/checkout/orders/%s/capture" % order_id, json={},
                headers={"PayPal-Request-Id": "cap-" + order_id, "Prefer": "return=representation"})


def refund(capture_id, amount, note, request_id):
    return call("POST", "/v2/payments/captures/%s/refund" % capture_id,
                json={"amount": {"currency_code": "USD", "value": amount}, "note_to_payer": note},
                headers={"PayPal-Request-Id": request_id})


def list_disputes(page_size=20):
    return call("GET", "/v1/customer/disputes", params={"page_size": page_size}).get("items", [])


def get_dispute(dispute_id):
    return call("GET", "/v1/customer/disputes/" + dispute_id)


def provide_evidence(dispute_id, pdf_bytes, notes, evidence_type="PROOF_FOR_SOFTWARE_OR_SERVICE_DELIVERED"):
    body = {"evidences": [{"evidence_type": evidence_type, "notes": notes[:2000],
                           "documents": [{"name": "evidence.pdf"}]}]}
    files = {"input": (None, json.dumps(body), "application/json"),
             "evidence-file": ("evidence.pdf", pdf_bytes, "application/pdf")}
    return call("POST", "/v1/customer/disputes/%s/provide-evidence" % dispute_id, files=files)


def make_offer(dispute_id, amount, note):
    return call("POST", "/v1/customer/disputes/%s/make-offer" % dispute_id, json={
        "note": note, "offer_amount": {"currency_code": "USD", "value": amount}, "offer_type": "REFUND"})


def adjudicate(dispute_id, outcome="SELLER_FAVOR"):
    return call("POST", "/v1/customer/disputes/%s/adjudicate" % dispute_id, json={"adjudication_outcome": outcome})


def verify_webhook(headers, event):
    h = {k.lower(): v for k, v in headers.items()}
    body = {"auth_algo": h.get("paypal-auth-algo"), "cert_url": h.get("paypal-cert-url"),
            "transmission_id": h.get("paypal-transmission-id"), "transmission_sig": h.get("paypal-transmission-sig"),
            "transmission_time": h.get("paypal-transmission-time"),
            "webhook_id": os.environ.get("PAYPAL_WEBHOOK_ID", ""), "webhook_event": event}
    try:
        return call("POST", "/v1/notifications/verify-webhook-signature", json=body).get("verification_status") == "SUCCESS"
    except PayPalError:
        return False


def create_webhook(url):
    return call("POST", "/v1/notifications/webhooks", json={"url": url, "event_types": [
        {"name": "CUSTOMER.DISPUTE.CREATED"}, {"name": "CUSTOMER.DISPUTE.UPDATED"}]})
