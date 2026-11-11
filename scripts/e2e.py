"""Buys the sample product in the PayPal sandbox with the sandbox buyer account, then downloads the file."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
BASE = os.environ.get("APP_URL", "http://localhost:5000")
SHOTS = os.environ.get("SHOTS_DIR", "shots")
os.makedirs(SHOTS, exist_ok=True)


def snap(page, name):
    page.screenshot(path="%s/%s.png" % (SHOTS, name))


def buy(page):
    """Runs the PayPal popup flow and returns the success page URL."""
    page.goto(BASE + "/")
    frame = page.frame_locator("iframe[title*='PayPal']").first
    btn = frame.locator("[data-funding-source='paypal']").first
    btn.wait_for(timeout=30000)
    snap(page, "e2e-1-store")
    with page.expect_popup(timeout=30000) as pop:
        btn.click()
    p = pop.value
    p.wait_for_load_state()
    p.fill("#email", os.environ["PAYPAL_SANDBOX_BUYER_EMAIL"], timeout=30000)
    if p.locator("#btnNext").count():
        p.click("#btnNext")
    p.fill("#password", os.environ["PAYPAL_SANDBOX_BUYER_PASSWORD"], timeout=30000)
    p.click("#btnLogin")
    snap(p, "e2e-2-paypal-review")
    p.locator("#payment-submit-btn, [data-testid='submit-button-initial'], button:has-text('Pay Now'), button:has-text('Complete Purchase'), button:has-text('Continue')").first.click(timeout=60000)
    page.wait_for_url("**/success/**", timeout=90000)
    return page.url


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.environ.get("HEADLESS", "0") == "1")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
        page = ctx.new_page()
        url = buy(page)
        order_id = url.rstrip("/").split("/")[-1]
        snap(page, "e2e-3-success")
        with page.expect_download() as d:
            page.click("#download")
        data = open(d.value.path(), "rb").read()
        assert data == open("products/notion-freelancer-starter-kit.pdf", "rb").read(), "file bytes differ"
        browser.close()
    if os.environ.get("DB_PATH"):
        import ledger
        events = [r["event"] for r in ledger.rows(order_id)]
        assert events[:4] == ["PURCHASE_CAPTURED", "DELIVERY_EMAIL_LOGGED", "LINK_OPENED", "FILE_DOWNLOADED"], events
        assert ledger.verify(order_id) == "ok"
    print(json.dumps({"order_id": order_id, "bytes": len(data)}))


if __name__ == "__main__":
    sys.exit(main())
