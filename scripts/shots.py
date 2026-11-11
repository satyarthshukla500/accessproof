"""Screenshots every page at 1280x800, 768x1024 and 390x844, logs console errors and failed requests,
and checks that nothing overlaps, is clipped sideways or makes the page scroll horizontally.
Usage: python scripts/shots.py <order id>   (set SHOT_HELP=1 to also send one chat message; needs the app running)"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
BASE = os.environ.get("APP_URL", "http://localhost:5000")
OUT = os.environ.get("SHOTS_DIR", "shots")
SIZES = {"1280": (1280, 800), "768": (768, 1024), "390": (390, 844)}
os.makedirs(OUT, exist_ok=True)

CHECK = """() => {
  const issues = [];
  const SEL = 'a,button,input,textarea,select,h1,h2,h3,p,li,label,code,img,iframe,dt,dd';
  const clipRect = (e) => {  // visible part of e after clipping by scrolling/hidden ancestors
    let r = e.getBoundingClientRect(), box = { l: r.left, t: r.top, r: r.right, b: r.bottom };
    for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.overflowX !== 'visible' || s.overflowY !== 'visible') {
        const q = p.getBoundingClientRect();
        box = { l: Math.max(box.l, q.left), t: Math.max(box.t, q.top), r: Math.min(box.r, q.right), b: Math.min(box.b, q.bottom) };
      }
    }
    return box;
  };
  const shown = (e) => { const s = getComputedStyle(e), r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; };
  const skip = (e) => e.closest('[data-overlap-ok], .ag-root-wrapper, .toasts, .typing, dialog:not([open])');
  const modal = document.querySelector('.drawer.open, dialog[open]');  // behind an open drawer or dialog only that panel counts
  const els = [...document.querySelectorAll(SEL)].filter((e) => shown(e) && !skip(e) && (!modal || modal.contains(e))).map((e) => ({ e, b: clipRect(e) })).filter((x) => x.b.r - x.b.l > 1 && x.b.b - x.b.t > 1);
  const name = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : '') + ' "' + (e.textContent || '').trim().slice(0, 24) + '"';
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    const a = els[i], b = els[j];
    if (a.e.contains(b.e) || b.e.contains(a.e)) continue;
    const w = Math.min(a.b.r, b.b.r) - Math.max(a.b.l, b.b.l), h = Math.min(a.b.b, b.b.b) - Math.max(a.b.t, b.b.t);
    if (w > 2 && h > 2) issues.push('overlap: ' + name(a.e) + ' x ' + name(b.e));
  }
  for (const e of document.querySelectorAll('body *')) {
    if (!shown(e) || skip(e) || e.closest('.msgs, .drawer-body')) continue;
    if (e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0 && !['svg', 'path', 'circle', 'rect', 'IFRAME'].includes(e.tagName.toUpperCase())) {
      const s = getComputedStyle(e);
      if (s.display !== 'inline' && !e.closest('svg')) issues.push('sideways overflow: ' + name(e) + ' ' + e.scrollWidth + '>' + e.clientWidth);
    }
  }
  if (document.documentElement.scrollWidth > window.innerWidth + 1) issues.push('page scrolls horizontally: ' + document.documentElement.scrollWidth + '>' + window.innerWidth);
  return issues.slice(0, 12);
}"""


def login(p):
    p.goto(BASE + "/login")
    p.fill("input[name=password]", os.environ["SELLER_PASSWORD"])
    p.click("button[type=submit]")
    p.wait_for_selector("#stats .stat", timeout=20000)
    p.wait_for_timeout(900)


def dash(tab):
    def go(p):
        login(p)
        if tab != "overview":
            p.click("#tab-" + tab)
            p.wait_for_selector("#grid-%s .ag-row" % tab, timeout=15000)
        p.wait_for_timeout(600)
    return go


def drawer(p):
    login(p)
    p.click("#hero button:has-text('See cited claims')")
    p.wait_for_selector("#drawer.open .claim", timeout=8000)
    p.wait_for_timeout(500)


def store(p):
    p.wait_for_selector("#paypal-button iframe", timeout=30000)
    p.wait_for_timeout(1500)


def ask(p):
    before = p.locator(".msg.bot").count()
    p.click("#quick button >> nth=0")
    p.wait_for_function("n => document.querySelectorAll('.msg.bot').length > n && !document.querySelector('.typing')", arg=before, timeout=120000)
    p.wait_for_timeout(800)


def token(order_id):
    """The same signed token the app puts in a buyer's links (the buyer pages need it)."""
    payload = base64.urlsafe_b64encode(("%s|%d" % (order_id, time.time() + 86400)).encode()).decode()
    return payload + "." + hmac.new(os.environ["APP_SECRET"].encode(), payload.encode(), hashlib.sha256).hexdigest()


def pages(order_id):
    t = token(order_id)
    out = [("store", "/", store), ("success", "/success/%s?t=%s" % (order_id, t), None), ("chat", "/order/%s/help?t=%s" % (order_id, t), None), ("login", "/login", None)]
    if os.environ.get("SHOT_HELP"):
        out.append(("chat-reply", "/order/%s/help?t=%s" % (order_id, t), ask))
    if os.environ.get("SELLER_PASSWORD") and not os.environ.get("NO_SELLER"):
        out += [("dash-" + n, "/login", dash(n)) for n in ("overview", "orders", "ledger", "help", "disputes")] + [("dash-drawer", "/login", drawer)]
    return out


def main():
    order_id = sys.argv[1]
    log, report = [], {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for size, (w, h) in SIZES.items():
            for name, path, action in pages(order_id):
                page = browser.new_context(viewport={"width": w, "height": h}).new_page()
                tag = "%s/%s" % (name, size)
                page.on("console", lambda m, t=tag: log.append("%s console %s: %s" % (t, m.type, m.text)) if m.type == "error" else None)
                page.on("requestfailed", lambda r, t=tag: log.append("%s requestfailed %s" % (t, r.url)) if "ABORTED" not in (r.failure or "") else None)
                page.on("response", lambda r, t=tag: log.append("%s http %s %s" % (t, r.status, r.url)) if r.status >= 400 else None)
                try:
                    page.goto(BASE + path)
                    if action:
                        action(page)
                    else:
                        page.wait_for_timeout(1500)
                    report[tag] = page.evaluate(CHECK)
                except Exception as e:
                    log.append("%s ERROR %s" % (tag, str(e)[:200]))
                    report[tag] = ["could not run: " + str(e)[:120]]
                page.screenshot(path="%s/%s-%s.png" % (OUT, name, size))
                page.context.close()
        browser.close()
    with open(OUT + "/console.log", "w") as f:
        f.write("\n".join(log) or "clean")
    with open(OUT + "/overlap-report.json", "w") as f:
        json.dump(report, f, indent=1)
    bad = {k: v for k, v in report.items() if v}
    print(json.dumps(log, indent=1) if log else "console clean")
    print(json.dumps(bad, indent=1) if bad else "overlap check passed on %d page views" % len(report))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
