"""Screenshots every page at desktop and phone size and logs console errors and failed requests."""
import json
import os
import sys

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
BASE = os.environ.get("APP_URL", "http://localhost:5000")
OUT = os.environ.get("SHOTS_DIR", "shots")
SIZES = {"desktop": (1280, 800), "mobile": (390, 844)}
os.makedirs(OUT, exist_ok=True)


def pages(order_id):
    """(name, path, action) where action(page) runs after load."""
    def login(p):
        p.goto(BASE + "/login")
        p.fill("input[name=password]", os.environ["SELLER_PASSWORD"])
        p.click("button[type=submit]")
        p.wait_for_url("**/dashboard")

    def ask(p):
        p.fill("textarea[name=message]", "I never got my download")
        p.click("#help-form button")
        p.wait_for_selector("#reply", timeout=120000)

    def tab(name):
        def go(p):
            login(p)
            p.wait_for_selector("#grid-orders .ag-row", timeout=15000)  # the page script must be ready before tabs work
            p.click("#tab-" + name)
            p.wait_for_selector("#grid-%s .ag-row" % name, timeout=15000)
        return go

    out = [("store", "/", None), ("success", "/success/" + order_id, None), ("help", "/order/%s/help" % order_id, None)]
    if os.environ.get("SHOT_HELP"):
        out.append(("help-reply", "/order/%s/help" % order_id, ask))
    if os.environ.get("SELLER_PASSWORD") and not os.environ.get("NO_SELLER"):
        out += [("login", "/login", None)]
        out += [("dashboard-" + n, "/login", tab(n)) for n in ("orders", "ledger", "help", "disputes")]
    return out


def main():
    order_id = sys.argv[1]
    log = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for size, (w, h) in SIZES.items():
            for name, path, action in pages(order_id):
                ctx = browser.new_context(viewport={"width": w, "height": h})
                page = ctx.new_page()
                page.on("console", lambda m, n=name, s=size: log.append("%s/%s console %s: %s" % (n, s, m.type, m.text)) if m.type == "error" else None)
                page.on("requestfailed", lambda r, n=name, s=size: log.append("%s/%s requestfailed %s" % (n, s, r.url)) if "ABORTED" not in (r.failure or "") else None)  # aborted = navigated away mid-load
                page.on("response", lambda r, n=name, s=size: log.append("%s/%s http %s %s" % (n, s, r.status, r.url)) if r.status >= 400 else None)
                try:
                    page.goto(BASE + path)
                    if action:
                        action(page)
                    page.wait_for_timeout(500)
                except Exception as e:
                    log.append("%s/%s ERROR %s" % (name, size, str(e)[:200]))
                page.screenshot(path="%s/%s-%s.png" % (OUT, name, size), full_page=True)
                ctx.close()
        browser.close()
    open(OUT + "/console.log", "w").write("\n".join(log) or "clean")
    print(json.dumps(log, indent=1) if log else "clean")


if __name__ == "__main__":
    main()
