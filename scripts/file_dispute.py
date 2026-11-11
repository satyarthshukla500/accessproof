"""Files an 'item not received' dispute in the PayPal sandbox Resolution Center as the sandbox buyer.
Set FILING_TXN to the sandbox transaction id of the purchase (the id in the Resolution Center URL).
The wizard keeps a saved draft, so each loop looks at what is on screen and does the next thing."""
import os

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
MESSAGE = "I paid for the digital guide but never received or opened the file. Please help."
URL = "https://www.sandbox.paypal.com/resolutioncenter/filing/%s/create?type=PAYMENT"


def fill_selects(page):
    for i in range(page.locator("select").count()):
        sel = page.locator("select").nth(i)
        if sel.input_value():
            continue
        labels = [o for o in sel.locator("option:not([disabled])").all_inner_texts() if o.strip()]
        pick = next((o for o in labels if o in ("Digital download", "Entertainment")), labels[0] if labels else None)
        if pick:
            sel.select_option(label=pick)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.environ.get("HEADLESS") == "1")
        page = browser.new_context(viewport={"width": 1280, "height": 1000}).new_page()
        page.goto("https://www.sandbox.paypal.com/signin")
        page.fill("#email", os.environ["PAYPAL_SANDBOX_BUYER_EMAIL"])
        if page.locator("#btnNext").count():
            page.click("#btnNext")
        page.fill("#password", os.environ["PAYPAL_SANDBOX_BUYER_PASSWORD"])
        page.click("#btnLogin")
        page.wait_for_url("**/myaccount/**", timeout=30000)
        page.goto(URL % os.environ["FILING_TXN"])
        for step in range(14):
            page.wait_for_timeout(4000)
            text = page.inner_text("body")
            print("step", step, page.url, "|", " ".join(text.split())[330:520])
            page.screenshot(path="shots/dispute-step-%d.png" % step)
            if page.get_by_role("button", name="Submit", exact=True).count():  # review page
                page.get_by_role("button", name="Submit", exact=True).first.click()
                page.wait_for_timeout(8000)
                page.screenshot(path="shots/dispute-submitted.png")
                print("submitted:", page.url, " ".join(page.inner_text("body").split())[300:600])
                break
            elif "Continue Reporting this Issue" in text:
                page.get_by_text("Continue Reporting this Issue").first.click()
            elif "I haven" in text and "Select the items" not in text and "We need a bit more" not in text:
                page.get_by_text("I haven").first.click()
            elif page.locator("textarea").count():
                page.locator("textarea").first.fill(MESSAGE)
                page.get_by_role("button", name="Continue").first.click()
            elif "Expected refund amount" in text:
                page.get_by_label("Enter amount (USD)").first.fill("29.00")
                page.get_by_role("button", name="Continue").first.click()
            elif page.locator("select").count():
                fill_selects(page)
                page.get_by_role("button", name="Continue").first.click()
            elif page.get_by_role("button", name="Continue").count():
                page.get_by_role("button", name="Continue").first.click()
            else:
                break
        browser.close()


if __name__ == "__main__":
    main()
