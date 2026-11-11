import time

import pytest

import db
import ledger


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    db.init()


def fill(order="o1"):
    for e in ("PURCHASE_CAPTURED", "DELIVERY_EMAIL_LOGGED", "LINK_OPENED", "FILE_DOWNLOADED"):
        ledger.add(order, e, "1.2.3.4", "agent", {"k": 1})


def test_chain_verifies():
    fill()
    assert [r["event"] for r in ledger.rows("o1")][0] == "PURCHASE_CAPTURED"
    assert ledger.verify("o1") == "ok"


@pytest.mark.parametrize("col,val", [("ip", "9.9.9.9"), ("ts", "2020-01-01"), ("event", "X"), ("detail", "{}"), ("ua", "evil")])
def test_tamper_breaks(col, val):
    fill()
    db.run("UPDATE ledger SET %s=? WHERE id=2" % col, (val,))
    assert ledger.verify("o1") == "broken"


def test_deleting_row_breaks():
    fill()
    db.run("DELETE FROM ledger WHERE id=2")
    assert ledger.verify("o1") == "broken"


def test_chains_are_per_order():
    fill("a")
    fill("b")
    assert ledger.verify("a") == ledger.verify("b") == "ok"


def test_tokens():
    import app
    t = app.sign("ord1")
    assert app.check(t) == "ord1"
    assert app.check(app.sign("ord1", now=time.time() - 8 * 86400)) is None  # expired
    payload, mac = t.split(".")
    assert app.check(payload + "." + "0" * 64) is None  # wrong mac
    other = app.sign("ord2").split(".")[0]
    assert app.check(other + "." + mac) is None  # forged payload
    assert app.check("garbage") is None
    assert app.check("") is None
