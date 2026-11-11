import json

import pytest
from reportlab import rl_config

import db
import evidence
import ledger
import limits
import paypal


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "s.db"))
    monkeypatch.setenv("SELLER_PASSWORD", "pw-test")
    import app as appmod
    db.init()
    limits._hits.clear()
    appmod.app.config["TESTING"] = True
    c = appmod.app.test_client()
    return c


HOOK = {"paypal-auth-algo": "SHA256withRSA", "paypal-cert-url": "https://x", "paypal-transmission-id": "1",
        "paypal-transmission-sig": "sig", "paypal-transmission-time": "2026-01-01T00:00:00Z"}


def login(c):
    c.post("/login", data={"password": "pw-test"})
    with c.session_transaction() as s:
        return s["csrf"]


def add_order():
    db.run("INSERT INTO orders(id,capture_id,payer_email,amount,currency) VALUES('o1','cap1','b@example.com','29.00','USD')")
    for e in ("PURCHASE_CAPTURED", "DELIVERY_EMAIL_LOGGED", "LINK_OPENED", "FILE_DOWNLOADED"):
        ledger.add("o1", e, "1.2.3.4", "Mozilla/5.0 " + "x" * 80)


def test_login_wrong_password(client):
    r = client.post("/login", data={"password": "nope"})
    assert b"Wrong password" in r.data
    assert client.get("/api/data").status_code == 302


def test_post_requires_csrf(client):
    csrf = login(client)
    assert client.post("/seller/disputes/sample").status_code == 400
    add_order()
    assert client.post("/seller/disputes/sample", headers={"X-CSRF": csrf}).status_code == 200


def test_unauthenticated_post_rejected(client):
    assert client.post("/seller/disputes/sync").status_code == 401


def test_webhook_rejects_unverified(client, monkeypatch):
    import paypal
    monkeypatch.setattr(paypal, "verify_webhook", lambda h, e: False)
    r = client.post("/webhooks/paypal", json={"event_type": "CUSTOMER.DISPUTE.CREATED", "resource": {"dispute_id": "D1"}}, headers=HOOK)
    assert r.status_code == 400
    assert db.query("SELECT * FROM disputes") == []


def test_webhook_verified_syncs(client, monkeypatch):
    import paypal
    monkeypatch.setattr(paypal, "verify_webhook", lambda h, e: True)
    monkeypatch.setattr(paypal, "get_dispute", lambda i: {"dispute_id": i, "reason": "OTHER", "status": "OPEN", "disputed_transactions": [{"seller_transaction_id": "cap1"}]})
    add_order()
    r = client.post("/webhooks/paypal", json={"event_type": "CUSTOMER.DISPUTE.CREATED", "resource": {"dispute_id": "D1"}}, headers=HOOK)
    assert r.status_code == 200
    assert db.one("SELECT order_id FROM disputes WHERE id='D1'")["order_id"] == "o1"


def test_sample_dispute_cannot_be_submitted(client, monkeypatch):
    import paypal
    called = []
    monkeypatch.setattr(paypal, "provide_evidence", lambda *a: called.append(a))
    csrf = login(client)
    add_order()
    client.post("/seller/disputes/sample", headers={"X-CSRF": csrf})
    did = db.one("SELECT id FROM disputes")["id"]
    r = client.post("/seller/disputes/%s/submit" % did, headers={"X-CSRF": csrf})
    assert r.status_code == 400 and called == []


def test_approve_refund_calls_paypal_once(client, monkeypatch):
    import paypal
    calls = []
    monkeypatch.setattr(paypal, "refund", lambda cap, amt, note, rid: calls.append((cap, amt)) or {"id": "R1", "status": "COMPLETED"})
    csrf = login(client)
    add_order()
    hid = db.run("INSERT INTO help_requests(order_id,outcome) VALUES('o1','refund_pending')")
    rid = db.run("INSERT INTO refund_requests(order_id,help_id,amount) VALUES('o1',?, '29.00')", (hid,))
    assert client.post("/seller/refund/%d/approve" % rid, headers={"X-CSRF": csrf}).status_code == 200
    assert client.post("/seller/refund/%d/approve" % rid, headers={"X-CSRF": csrf}).status_code == 404
    assert calls == [("cap1", "29.00")]
    assert ledger.rows("o1")[-1]["event"] == "REFUND_APPROVED"


def test_pdf_has_event_table_and_escapes_text(monkeypatch):
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    rows = [{"id": i, "ts": "2026-01-01T00:00:0%d+00:00" % i, "event": e, "ip": "1.2.3.4", "ua": "UA " * 40}
            for i, e in enumerate(["PURCHASE_CAPTURED", "FILE_DOWNLOADED"], 1)]
    pack = {"summary": "Downloaded <b>once</b> & done", "claims": [{"text": "File downloaded", "event_ids": [2]}]}
    pdf = evidence.build_pdf({"id": "D1", "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "amount": "29.00", "currency": "USD"},
                             {"id": "o1", "capture_id": "cap1"}, rows, pack, "ok")
    assert pdf.startswith(b"%PDF")
    for needle in (b"PURCHASE_CAPTURED", b"FILE_DOWNLOADED", b"cap1", b"D1", b"#2"):
        assert needle in pdf


def paypal_dispute(raw_links):
    """Inserts a dispute that came from PayPal with a built evidence pack."""
    add_order()
    raw = {"dispute_id": "D9", "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "status": "WAITING_FOR_SELLER_RESPONSE",
           "dispute_life_cycle_stage": "INQUIRY", "dispute_amount": {"currency_code": "USD", "value": "29.00"},
           "disputed_transactions": [{"seller_transaction_id": "cap1"}], "links": raw_links}
    import seller
    seller.upsert_dispute(raw)
    pack = {"covered": True, "summary": "sum", "claims": [{"text": "downloaded", "event_ids": [4]}], "recommendation": "SUBMIT_EVIDENCE"}
    db.run("UPDATE disputes SET pack=? WHERE id='D9'", (json.dumps(pack),))


def test_submit_needs_provide_evidence_link(client, monkeypatch):
    import paypal
    called = []
    monkeypatch.setattr(paypal, "provide_evidence", lambda *a: called.append(a))
    csrf = login(client)
    paypal_dispute([])
    assert client.post("/seller/disputes/D9/submit", headers={"X-CSRF": csrf}).status_code == 400 and called == []


def test_submit_success_survives_refresh_failure(client, monkeypatch):
    import paypal
    monkeypatch.setattr(paypal, "provide_evidence", lambda *a: {})

    def down(i):
        raise paypal.PayPalError(500, "x")
    monkeypatch.setattr(paypal, "get_dispute", down)
    csrf = login(client)
    paypal_dispute([{"rel": "provide-evidence", "href": "x"}])
    r = client.post("/seller/disputes/D9/submit", headers={"X-CSRF": csrf})
    assert r.status_code == 200
    assert ledger.rows("o1")[-1]["event"] == "EVIDENCE_SUBMITTED"
    assert db.one("SELECT last_result FROM disputes")["last_result"].startswith("Evidence submitted")


def test_adjudicate_blocked_without_link_and_for_sample(client, monkeypatch):
    import paypal
    called = []
    monkeypatch.setattr(paypal, "adjudicate", lambda *a: called.append(a))
    csrf = login(client)
    paypal_dispute([])
    assert client.post("/seller/disputes/D9/adjudicate", headers={"X-CSRF": csrf}).status_code == 400
    client.post("/seller/disputes/sample", headers={"X-CSRF": csrf})
    sid = db.one("SELECT id FROM disputes WHERE source='sample'")["id"]
    assert client.post("/seller/disputes/%s/adjudicate" % sid, headers={"X-CSRF": csrf}).status_code == 400
    assert called == []


def test_offer_only_in_inquiry_stage(client, monkeypatch):
    import paypal
    called = []
    monkeypatch.setattr(paypal, "make_offer", lambda *a: called.append(a))
    csrf = login(client)
    paypal_dispute([])
    db.run("UPDATE disputes SET stage='CHARGEBACK'")
    assert client.post("/seller/disputes/D9/offer", headers={"X-CSRF": csrf}).status_code == 400 and called == []


def test_seed_order_refund_never_reaches_paypal(client, monkeypatch):
    import paypal
    called = []
    monkeypatch.setattr(paypal, "refund", lambda *a: called.append(a))
    csrf = login(client)
    db.run("INSERT INTO orders(id,capture_id,amount,currency,source) VALUES('s1','SEEDCAP','29.00','USD','seed')")
    rid = db.run("INSERT INTO refund_requests(order_id,amount) VALUES('s1','29.00')")
    assert client.post("/seller/refund/%d/approve" % rid, headers={"X-CSRF": csrf}).status_code == 400 and called == []


def test_every_seller_post_route_requires_login_and_csrf(client):
    import app as appmod
    posts = [r for r in appmod.app.url_map.iter_rules() if r.rule.startswith("/seller") and "POST" in r.methods]
    assert len(posts) >= 7
    csrf = login(client)
    for r in posts:
        url = r.rule
        for arg in r.arguments:
            url = url.replace("<int:%s>" % arg, "1").replace("<%s>" % arg, "x")
        assert client.post(url, headers={"X-CSRF": "wrong"}).status_code == 400, url
        client.get("/logout")
        with client.session_transaction() as s:
            s.clear()
        assert client.post(url).status_code == 401, url
        login(client)
    assert csrf


def test_pdf_survives_control_characters():
    pack = {"summary": "s", "claims": []}
    rows = [{"id": 1, "ts": "t", "event": "E", "ip": "1.1.1.1", "ua": "bad\x00\x0bagent"}]
    assert evidence.build_pdf({"id": "D", "reason": "r", "amount": "1", "currency": "USD"}, {"id": "o", "capture_id": "c"}, rows, pack, "ok")[:4] == b"%PDF"


def test_requested_evidence_type_comes_from_paypal():
    import seller
    raw = {"evidences": [{"evidence_type": "CREATE", "source": "SUBMITTED_BY_BUYER"},
                         {"evidence_type": "PROOF_OF_FULFILLMENT", "source": "REQUESTED_FROM_SELLER"}]}
    assert seller.requested_type(raw) == "PROOF_OF_FULFILLMENT"
    assert seller.requested_type({}) == "PROOF_FOR_SOFTWARE_OR_SERVICE_DELIVERED"


def test_login_is_throttled_after_five_failures(client):
    import limits
    limits._hits.clear()
    for _ in range(5):
        assert client.post("/login", data={"password": "nope"}).status_code == 200
    assert client.post("/login", data={"password": "nope"}).status_code == 429
    assert client.post("/login", data={"password": "pw-test"}).status_code == 429  # locked out for the window
    limits._hits.clear()
    assert client.post("/login", data={"password": "pw-test"}).status_code == 302


def test_stats_skip_seed_rows_and_real_disputes_sort_first(client):
    import seller
    csrf = login(client)
    paypal_dispute([])  # also adds order o1
    db.run("INSERT INTO help_requests(order_id,outcome,source) VALUES('o1','deflected','real')")
    db.run("INSERT INTO help_requests(order_id,outcome,source) VALUES('o1','deflected','seed')")
    client.post("/seller/disputes/sample", headers={"X-CSRF": csrf})
    db.run("UPDATE disputes SET last_result='Evidence submitted to PayPal' WHERE id='D9'")
    db.run("INSERT INTO disputes(id,source,last_result,created_at) VALUES('S1','seed','Evidence submitted to PayPal','2030-01-01')")
    data = client.get("/api/data").get_json()
    assert data["stats"] == {"deflected": 1, "filed": 1, "fees": 15, "refunds": 0}
    assert data["disputes"][0]["id"] == "D9" and seller  # real rows first


def test_offer_button_only_while_paypal_waits_for_seller(client):
    csrf = login(client)
    paypal_dispute([])
    assert client.get("/api/data").get_json()["disputes"][0]["can_offer"] is True
    db.run("UPDATE disputes SET status='WAITING_FOR_BUYER_RESPONSE'")
    assert client.get("/api/data").get_json()["disputes"][0]["can_offer"] is False
    assert csrf


def test_seller_ledger_rows_name_the_seller(client, monkeypatch):
    import paypal
    monkeypatch.setattr(paypal, "refund", lambda *a: {"id": "R1", "status": "COMPLETED"})
    csrf = login(client)
    add_order()
    rid = db.run("INSERT INTO refund_requests(order_id,amount) VALUES('o1','29.00')")
    client.post("/seller/refund/%d/approve" % rid, headers={"X-CSRF": csrf})
    last = ledger.rows("o1")[-1]
    assert last["event"] == "REFUND_APPROVED" and last["ip"] == "seller" and last["ua"] == "seller dashboard"
    assert ledger.verify("o1") == "ok"


def test_webhook_without_paypal_headers_never_calls_paypal(client, monkeypatch):
    import paypal
    called = []
    monkeypatch.setattr(paypal, "verify_webhook", lambda h, e: called.append(1) or True)
    assert client.post("/webhooks/paypal", data="x").status_code == 400
    assert client.post("/webhooks/paypal", json={"a": 1}).status_code == 400
    assert client.post("/webhooks/paypal", data="[" * 60000 + "]" * 60000, headers=dict(HOOK, **{"Content-Type": "application/json"})).status_code in (400, 413)
    assert client.post("/webhooks/paypal", data="[1]", headers=dict(HOOK, **{"Content-Type": "application/json"})).status_code == 400
    assert called == []


def test_seller_session_expires(client, monkeypatch):
    import time
    login(client)
    assert client.get("/api/data").status_code == 200
    monkeypatch.setattr(time, "time", lambda: 1e10)
    assert client.get("/api/data").status_code == 302


def test_sample_dispute_is_loaded_once_per_kind(client):
    csrf = login(client)
    add_order()
    first = client.post("/seller/disputes/sample", headers={"X-CSRF": csrf}).get_json()
    again = client.post("/seller/disputes/sample", headers={"X-CSRF": csrf}).get_json()
    snad = client.post("/seller/disputes/sample?reason=snad", headers={"X-CSRF": csrf}).get_json()
    assert first["message"].startswith("Sample dispute added") and again["message"] == "That sample is already loaded"
    assert snad["message"].startswith("Sample dispute added")
    assert db.one("SELECT COUNT(*) n FROM disputes")["n"] == 2


def test_refund_request_id_is_unique_per_capture(client, monkeypatch):
    import paypal
    keys = []
    monkeypatch.setattr(paypal, "refund", lambda cap, amt, note, rid: keys.append(rid) or {"id": "R", "status": "COMPLETED"})
    csrf = login(client)
    add_order()
    rid = db.run("INSERT INTO refund_requests(order_id,amount) VALUES('o1','29.00')")
    client.post("/seller/refund/%d/approve" % rid, headers={"X-CSRF": csrf})
    assert keys == ["refund-%d-cap1" % rid]  # a database that restarts its ids cannot reuse an old PayPal-Request-Id


def test_logout_revokes_a_copied_cookie(client):
    login(client)
    with client.session_transaction() as s:
        copied = dict(s)
    client.post("/logout", headers={"X-CSRF": copied["csrf"]})
    with client.session_transaction() as s:
        s.update(copied)  # replay the cookie from before the logout
    assert client.get("/api/data").status_code in (302, 401)


def test_login_is_limited_overall_not_only_per_address(client):
    for _ in range(300):
        limits.add("login:all")
    assert client.post("/login", data={"password": "pw-test"}).status_code == 429


def test_second_refund_for_an_order_is_refused(client, monkeypatch):
    monkeypatch.setattr(paypal, "refund", lambda *a: {"id": "R", "status": "COMPLETED"})
    csrf = login(client)
    add_order()
    first = db.run("INSERT INTO refund_requests(order_id,amount) VALUES('o1','29.00')")
    second = db.run("INSERT INTO refund_requests(order_id,amount) VALUES('o1','29.00')")
    assert client.post("/seller/refund/%d/approve" % first, headers={"X-CSRF": csrf}).status_code == 200
    assert client.post("/seller/refund/%d/approve" % second, headers={"X-CSRF": csrf}).status_code == 409


def test_filing_sends_the_chain_head_to_paypal(client, monkeypatch):
    sent = []
    monkeypatch.setattr(paypal, "provide_evidence", lambda *a: sent.append(a))
    monkeypatch.setattr(paypal, "get_dispute", lambda i: (_ for _ in ()).throw(paypal.PayPalError(500, "x")))
    csrf = login(client)
    paypal_dispute([{"rel": "provide-evidence", "href": "x"}])
    head = ledger.head("o1")
    assert client.post("/seller/disputes/D9/submit", headers={"X-CSRF": csrf}).status_code == 200
    assert "Ledger chain head at filing: " + head in sent[0][2]
