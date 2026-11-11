"""Registers the dispute webhook for a public URL and saves PAYPAL_WEBHOOK_ID to .env.
Usage: python scripts/register_webhook.py https://your-app.onrender.com"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
import paypal  # noqa: E402

if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
    sys.exit("usage: python scripts/register_webhook.py https://your-public-url")
hook = paypal.create_webhook(sys.argv[1].rstrip("/") + "/webhooks/paypal")
with open(".env", "a") as f:
    f.write("\nPAYPAL_WEBHOOK_ID=%s\n" % hook["id"])
print("registered webhook", hook["id"], "- also set PAYPAL_WEBHOOK_ID on Render")
