import re
import sqlite3

import pytest

import db
import limits
import ledger


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "v.db"))
    import app as appmod
    db.init()
    appmod.app.config["TESTING"] = True
    limits._hits.clear()
    return appmod, appmod.app.test_client()


def demo_order(appmod, c):
    c.post("/api/demo-order")
    oid = db.one("SELECT id FROM orders WHERE source='demo'")["id"]
    ledger.add(oid, "LINK_OPENED", "203.0.113.9", "SecretBrowser/9.9")
    ledger.add(oid, "FILE_DOWNLOADED", "203.0.113.9", "SecretBrowser/9.9")
    return oid


def test_intact_record_is_verified(ctx):
    appmod, c = ctx
    oid = demo_order(appmod, c)
    r = c.get("/verify/" + appmod.proof_code(oid))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Verified" in html and "has not been changed since it was written" in html
    assert "Payment captured" in html and "File downloaded" in html
    assert "This record was changed" not in html


def test_changed_row_is_reported_with_its_step(ctx):
    appmod, c = ctx
    oid = demo_order(appmod, c)
    rows = ledger.rows(oid)
    con = sqlite3.connect(db.path())
    con.execute("UPDATE ledger SET ts='2020-01-01T00:00:00+00:00' WHERE id=?", (rows[1]["id"],))
    con.commit()
    con.close()
    r = c.get("/verify/" + appmod.proof_code(oid))
    html = r.get_data(as_text=True)
    assert "This record was changed after it was written" in html
    assert "is step 2" in html
    assert 'class="bad"' in html and "block bad" in html
    assert "has not been changed since it was written" not in html


def test_unknown_or_forged_code_finds_nothing(ctx):
    appmod, c = ctx
    oid = demo_order(appmod, c)
    for code in ("nope", oid + ".0000000000000000000", "DEMO-X." + appmod.proof_code(oid).split(".")[1], ""):
        r = c.get("/verify/" + code) if code else c.get("/verify/%20")
        assert r.status_code == 404 and "No record found" in r.get_data(as_text=True)


def test_page_shows_no_ip_agent_email_or_buyer_token(ctx):
    appmod, c = ctx
    oid = demo_order(appmod, c)
    html = c.get("/verify/" + appmod.proof_code(oid)).get_data(as_text=True)
    for secret in ("203.0.113.9", "SecretBrowser", "demo@example.invalid", appmod.sign(oid), "?t="):
        assert secret not in html
    assert not re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", html)


def test_proof_code_is_not_the_buyer_token(ctx):
    appmod, c = ctx
    oid = demo_order(appmod, c)
    code = appmod.proof_code(oid)
    assert appmod.check(code) is None and c.get("/d/" + code).status_code == 403
    assert c.get("/success/%s?t=%s" % (oid, code)).status_code == 404


def test_form_redirects_a_pasted_link_and_success_page_links_to_proof(ctx):
    appmod, c = ctx
    oid = demo_order(appmod, c)
    code = appmod.proof_code(oid)
    assert c.get("/verify").status_code == 200
    r = c.get("/verify?code=https://example.org/verify/" + code)
    assert r.status_code == 302 and r.headers["Location"] == "/verify/" + code
    page = c.get("/success/%s?t=%s" % (oid, appmod.sign(oid))).get_data(as_text=True)
    assert 'href="/verify/%s"' % code in page and "Share proof link" in page
    chat = c.get("/order/%s/help?t=%s" % (oid, appmod.sign(oid))).get_data(as_text=True)
    assert 'href="/verify/%s"' % code in chat


def test_seed_orders_have_no_public_record(ctx):
    appmod, c = ctx
    db.run("INSERT INTO orders(id,payer_email,amount,currency,created_at,source) VALUES('SEED-1','s@example.com','29.00','USD',datetime('now'),'seed')")
    assert c.get("/verify/" + appmod.proof_code("SEED-1")).status_code == 404
