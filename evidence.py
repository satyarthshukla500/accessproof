import io
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ledger import EVENT_LABELS

STYLES = getSampleStyleSheet()
SMALL = ParagraphStyle("small", parent=STYLES["BodyText"], fontSize=8, leading=10)


def p(text, style="BodyText"):
    """Paragraph with escaped text; model and buyer text must never be parsed as markup."""
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(text))
    return Paragraph(escape(clean), SMALL if style == "small" else STYLES[style])


def event_cell(event):
    """The plain-language name first, the stored event key small underneath."""
    return Paragraph("%s<br/><font size=6 color='#888888'>%s</font>" % (escape(EVENT_LABELS.get(event, event)), escape(event)), SMALL)


def header(canvas, doc):
    """Brand mark and wordmark at the top of every page."""
    x, y = 0.7 * inch, letter[1] - 0.66 * inch
    navy, mint = colors.HexColor("#0B1B33"), colors.HexColor("#2DD4BF")
    canvas.saveState()
    canvas.setFillColor(navy)
    canvas.roundRect(x, y, 24, 24, 6, fill=1, stroke=0)
    canvas.setStrokeColor(mint)
    canvas.setLineWidth(1.2)
    canvas.roundRect(x + 4, y + 8, 7, 8, 2, fill=0, stroke=1)
    canvas.line(x + 11, y + 12, x + 13, y + 12)
    canvas.setFillColor(mint)
    canvas.roundRect(x + 13, y + 8, 7, 8, 2, fill=1, stroke=0)
    canvas.setFillColor(navy)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(x + 32, y + 8, "Access")
    canvas.setFillColor(colors.HexColor("#0F766E"))
    canvas.drawString(x + 32 + canvas.stringWidth("Access", "Helvetica-Bold", 13), y + 8, "Proof")
    canvas.restoreState()


def short(ua, n=70):
    return ua if len(ua) <= n else ua[: n - 3] + "..."


def build_pdf(dispute, order, rows, pack, chain):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title="Evidence pack", leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=1.0 * inch, bottomMargin=0.7 * inch)
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
        data.append([p(r["id"], "small"), p(r["ts"][:19].replace("T", " "), "small"), event_cell(r["event"]), p(r["ip"], "small"), p(short(r["ua"]), "small")])
    t = Table(data, colWidths=[0.4 * inch, 1.5 * inch, 1.7 * inch, 1.0 * inch, 2.4 * inch], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    head = rows[-1]["hash"] if rows and "hash" in rows[-1].keys() else "none"
    out += [t, Spacer(1, 8), p("Each ledger row stores the hash of the previous row, so changing any row breaks the chain. Chain status: %s. Chain head (hash of the last row): %s. "
                               "DELIVERY_EMAIL_LOGGED records that the download link was issued for the payer's address on file; no email service is connected." % (chain, head), "small")]
    doc.build(out, onFirstPage=header, onLaterPages=header)
    return buf.getvalue()
