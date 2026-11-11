import importlib.util
import json
import os

import db
import ledger


def load_seed():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "seed.py")
    spec = importlib.util.spec_from_file_location("seed_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_real_case_loads_with_a_valid_chain_and_citable_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "s.db"))
    db.init()
    seed = load_seed()
    assert seed.load_real_case() is True
    d = db.one("SELECT * FROM disputes WHERE source='paypal'")
    ids = {r["id"] for r in ledger.rows(d["order_id"])}
    assert ledger.verify(d["order_id"]) == "ok"
    assert all(set(c["event_ids"]) <= ids for c in json.loads(d["pack"])["claims"])
    assert seed.load_real_case() is False  # a second load changes nothing
    seed.seed()
    assert db.one("SELECT COUNT(*) n FROM disputes")["n"] == 3


def test_fixture_has_no_email_addresses():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "real_case.json")
    text = open(path, encoding="utf-8").read()
    import re
    assert set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)) <= {"sandbox-buyer@example.invalid"}
