import io
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

STYLES = getSampleStyleSheet()
SMALL = ParagraphStyle("small", parent=STYLES["BodyText"], fontSize=8, leading=10)


def p(text, style="BodyText"):
    """Paragraph with escaped text; model and buyer text must never be parsed as markup."""
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(text))
    return Paragraph(escape(clean), SMALL if style == "small" else STYLES[style])


def short(ua, n=70):
    return ua if len(ua) <= n else ua[: n - 3] + "..."


def build_pdf(dispute, order, rows, pack, chain):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title="Evidence pack", leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    out = [p("Evidence pack: proof of delivery of a digital product", "Title")]
    if dispute.get("source") in ("sample", "seed"):
        out.append(p("SAMPLE dispute (not from PayPal): this pack was built for demonstration.", "Heading3"))
    head = [["Order", order["id"]], ["PayPal capture ID", order["capture_id"]], ["Dispute ID", dispute["id"]],
            ["Dispute reason", dispute["reason"].replace("MERCHANDISE_OR_SERVICE_", "").replace("_", " ").lower()], ["Amount", "%s %s" % (dispute["amount"], dispute["currency"])],
            ["Access ledger chain", chain]]
    t = Table([[p(a, "small"), p(b, "small")] for a, b in head], colWidths=[1.6 * inch, 5.4 * inch])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    out += [t, Spacer(1, 12), p("Summary", "Heading2"), p(pack["summary"]), Spacer(1, 8), p("Claims and the ledger events that prove them", "Heading2")]
    for i, c in enumerate(pack["claims"], 1):
        out.append(p("%d. %s [ledger events: %s]" % (i, c["text"], ", ".join("#%d" % e for e in c["event_ids"]))))
    out += [Spacer(1, 8), p("Access ledger (UTC)", "Heading2")]
    data = [[p(h, "small") for h in ("ID", "Time (UTC)", "Event", "IP", "User agent")]]
    for r in rows:
        data.append([p(r["id"], "small"), p(r["ts"][:19].replace("T", " "), "small"), p(r["event"], "small"), p(r["ip"], "small"), p(short(r["ua"]), "small")])
    t = Table(data, colWidths=[0.4 * inch, 1.5 * inch, 1.7 * inch, 1.0 * inch, 2.4 * inch], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    out += [t, Spacer(1, 8), p("Each ledger row stores the hash of the previous row, so changing any row breaks the chain. Chain status: %s. DELIVERY_EMAIL_LOGGED records that the download link was issued for the payer's address on file; no email service is connected." % chain, "small")]
    doc.build(out)
    return buf.getvalue()
