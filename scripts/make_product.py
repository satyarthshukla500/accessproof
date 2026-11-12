"""Builds the sample digital product: a designed, multi-page Notion guide for freelancers (products/notion-freelancer-starter-kit.pdf)."""
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

NAVY, TEAL, BLUE, INK, MUTED, LINE, TINT = "#0B1B33", "#0F9D8A", "#2563EB", "#14213D", "#5B6B85", "#D9E1EC", "#EEF7F6"
W, H = letter
M = 0.85 * inch
TITLE = "Notion Freelancer Starter Kit"

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=colors.HexColor(NAVY), spaceAfter=6)
KICK = ParagraphStyle("kick", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.HexColor(TEAL), spaceAfter=4)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=colors.HexColor(NAVY), spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=15.5, textColor=colors.HexColor(INK), spaceAfter=8, alignment=TA_LEFT)
LEAD = ParagraphStyle("lead", parent=BODY, fontSize=12.5, leading=18, textColor=colors.HexColor(MUTED), spaceAfter=14)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=9, leading=12.5, textColor=colors.HexColor(MUTED), spaceAfter=0)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9.5, leading=13, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
CODE = ParagraphStyle("code", fontName="Courier", fontSize=8.8, leading=12.5, textColor=colors.HexColor(NAVY))
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=14, bulletIndent=2, spaceAfter=4)


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, BUL, bulletText="•") for t in items]


def props(rows, head=("Property", "Type", "What it is for")):
    data = [[Paragraph(h, CELLB) for h in head]] + [[Paragraph(r[0], CELLB), Paragraph(r[1], CELL), Paragraph(r[2], CELL)] for r in rows]
    t = Table(data, colWidths=[1.55 * inch, 1.3 * inch, W - 2 * M - 2.85 * inch], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(TINT)), ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE))]))
    return t


def callout(title, text, color=TEAL):
    t = Table([[Paragraph("<b>%s</b><br/>%s" % (title, text), CELL)]], colWidths=[W - 2 * M])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(TINT)), ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(color)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    return t


def code(lines):
    t = Table([[Paragraph("<br/>".join(ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;") for ln in lines), CODE)]], colWidths=[W - 2 * M])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F6FB")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


class Check(Flowable):
    """A tick box with a label, drawn by hand so it prints in any viewer."""

    def __init__(self, text):
        super().__init__()
        self.para = Paragraph(text, CELL)

    def wrap(self, aw, ah):
        w, h = self.para.wrap(aw - 26, ah)
        self.height = max(h, 14) + 7
        self.width = aw
        return aw, self.height

    def draw(self):
        c = self.canv
        c.setStrokeColor(colors.HexColor(TEAL))
        c.setLineWidth(1.3)
        c.roundRect(2, self.height - 15, 11, 11, 2.5, stroke=1, fill=0)
        self.para.drawOn(c, 24, self.height - 3 - self.para.height + 1)


def chapter(num, title, lead):
    return [p("CHAPTER %s" % num if num else "CONTENTS", KICK), p(title, H1), p(lead, LEAD)]


def on_page(c, doc):
    if doc.page == 1:
        return
    c.saveState()
    c.setFillColor(colors.HexColor(NAVY))
    c.rect(0, H - 0.42 * inch, W, 0.42 * inch, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#2DD4BF"))
    c.rect(0, H - 0.42 * inch, 0.35 * inch, 0.42 * inch, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(0.6 * inch, H - 0.27 * inch, TITLE)
    c.setFillColor(colors.HexColor(MUTED))
    c.setFont("Helvetica", 8.5)
    c.drawString(M, 0.5 * inch, "Keep it simple. Review it every Friday.")
    c.drawRightString(W - M, 0.5 * inch, "Page %d" % doc.page)
    c.restoreState()


def cover(c, doc):
    c.saveState()
    c.setFillColor(colors.HexColor(NAVY))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#122A4D"))
    c.circle(W - 0.6 * inch, H - 0.9 * inch, 2.6 * inch, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#2DD4BF"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(M, H - 1.5 * inch, "STARTER KIT  •  VERSION 1.0")
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 44)
    for i, line in enumerate(("Notion", "Freelancer", "Starter Kit")):
        c.drawString(M, H - 2.5 * inch - i * 0.78 * inch, line)
    c.setFillColor(colors.HexColor("#B7C3D6"))
    c.setFont("Helvetica", 15)
    c.drawString(M, H - 5.15 * inch, "Run your clients, projects and invoices from one calm workspace.")
    c.drawString(M, H - 5.5 * inch, "Five databases, ready-to-paste templates and a Friday review.")
    y = 1.5 * inch
    for i in range(3):  # three linked blocks, the product's motif
        x = M + i * 1.25 * inch
        c.setStrokeColor(colors.HexColor("#2DD4BF"))
        c.setLineWidth(3)
        if i < 2:
            c.line(x + 0.78 * inch, y + 0.25 * inch, x + 1.25 * inch, y + 0.25 * inch)
        c.setFillColor(colors.HexColor("#2DD4BF") if i == 2 else colors.HexColor(NAVY))
        c.roundRect(x, y, 0.78 * inch, 0.5 * inch, 10, stroke=1, fill=1)
    c.restoreState()


def build(path, sample=False):
    doc = BaseDocTemplate(path, pagesize=letter, title=TITLE, author="AccessProof demo store", subject="A practical Notion workspace for freelancers")
    body = Frame(M, 0.85 * inch, W - 2 * M, H - 1.85 * inch, id="body", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    full = Frame(0, 0, W, H, id="cover")
    doc.addPageTemplates([PageTemplate(id="cover", frames=[full], onPage=cover, autoNextPageTemplate="main"), PageTemplate(id="main", frames=[body], onPage=on_page)])
    S = []
    cut = []  # where the sample ends: after chapter 1

    S += [Spacer(1, 1), PageBreak()]

    # contents
    S += chapter("", "What is inside", "Read it in one sitting, then build one chapter a day. You will be running your work from Notion by the end of the week.")
    toc = [("1", "Set up in twenty minutes", "The workspace, the five databases and how they connect"), ("2", "Clients", "Who they are, what is next, when to follow up"),
           ("3", "Projects", "Scope, stage, fee and due date, always in view"), ("4", "Invoices", "Get paid on time, with formulas that nag for you"),
           ("5", "Tasks", "Today, this week, waiting on a client"), ("6", "The Friday review", "A fifteen minute habit that keeps everything honest"),
           ("7", "Copy-paste templates", "Proposal, kick-off, reminder and wrap-up messages"), ("8", "Formula cheat sheet", "The nine formulas this kit relies on"),
           ("9", "Questions and mistakes", "What goes wrong and how to fix it")]
    rows = [[Paragraph("<b>%s</b>" % n, CELLB), Paragraph("<b>%s</b><br/><font color='%s'>%s</font>" % (t, MUTED, d), CELL)] for n, t, d in toc]
    t = Table(rows, colWidths=[0.45 * inch, W - 2 * M - 0.45 * inch])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    S += [t, Spacer(1, 18), callout("Who this is for", "Freelancers who sell their time or their work: designers, developers, writers, consultants, editors. If you have more than two clients and an inbox you do not trust, this kit is for you."), PageBreak()]

    # 1 setup
    S += chapter(1, "Set up in twenty minutes", "One page, five databases, three rules. Nothing else.")
    S += [p("Create a page called <b>Studio</b>. Inside it, create five full-page databases: <b>Clients</b>, <b>Projects</b>, <b>Invoices</b>, <b>Tasks</b> and <b>Notes</b>. Connect them with relations so that a task knows its project, a project knows its client and an invoice knows both.")]
    S += [props([("Clients", "Database", "Everyone you work for, and every lead you are chasing"), ("Projects", "Database", "One row per piece of paid work, related to a client"),
                 ("Invoices", "Database", "One row per invoice, related to a client and a project"), ("Tasks", "Database", "Small steps, related to a project"), ("Notes", "Database", "Meetings, calls and ideas, related to a client")], ("Database", "Kind", "Holds"))]
    S += [p("The three rules", H2)] + bullets(["<b>One home for everything.</b> If it is not in Studio, it does not exist.", "<b>Relations over copies.</b> Never type a client name twice; relate to the client row.",
                                               "<b>Every row has a next step.</b> A row without a next step is clutter."])
    S += [Spacer(1, 6), callout("Tip", "Give every database a short icon and colour. You will recognise them faster than words, and your sidebar will stay readable."), PageBreak()]
    cut.append(len(S))

    # 2 clients
    S += chapter(2, "Clients", "The place you open first every morning.")
    S += [props([("Name", "Title", "Person or company"), ("Status", "Select", "Lead, Active, Paused, Past"), ("Email", "Email", "Where invoices go"), ("Next follow-up", "Date", "The next time you must write to them"),
                 ("Projects", "Relation", "Links to the Projects database"), ("Total billed", "Rollup", "Sum of Amount from related Invoices"), ("Notes", "Text", "How they like to work")])]
    S += [p("Views to add", H2)] + bullets(["<b>Board by Status</b> to see your pipeline at a glance.", "<b>Table: Follow up this week</b>, filtered to Next follow-up is within the next 7 days.", "<b>Gallery</b> with a cover image per client for a friendlier view."])
    S += [p("A client page template", H2), code(["Client: [name]        Status: Active", "Contact: [person], [email], best time to reach", "How they like updates: [email / call / shared doc]", "Payment terms: [14 days]   Currency: [USD]", "Next follow-up: [date]", "", "Projects  (linked view)", "Invoices  (linked view)", "Notes     (linked view)"])]
    S += [Spacer(1, 8), callout("Why it works", "The follow-up date turns your client list from a phone book into a to-do list. Once a week you filter for this week, write the messages and move the dates.")]
    S += [PageBreak()]

    # 3 projects
    S += chapter(3, "Projects", "Scope, stage, fee and due date, always in view.")
    S += [props([("Project", "Title", "Short, specific name"), ("Client", "Relation", "Links to Clients"), ("Stage", "Select", "Brief, Draft, Review, Revisions, Done"), ("Due", "Date", "The date you promised"),
                 ("Fee", "Number", "Agreed price"), ("Invoiced", "Rollup", "Sum of Amount from related Invoices"), ("Left to bill", "Formula", "Fee minus Invoiced")])]
    S += [p("Views to add", H2)] + bullets(["<b>Board by Stage</b> is your production line.", "<b>Calendar on Due</b> shows crunch weeks before they arrive.", "<b>Table: Not done</b>, sorted by Due, filtered to Stage is not Done."])
    S += [p("The project brief", H2), p("Paste this at the top of every new project page and fill it in before you start. Ten minutes here saves ten hours later.")]
    S += [code(["Goal: what must be true when this is finished?", "Deliverables: list each file, page or feature", "Not included: what we agreed not to do", "Dates: kick-off / first draft / final", "Feedback: who gives it, how many rounds", "Fee and payment: amount, deposit, due date"])]
    S += [PageBreak()]

    # 4 invoices
    S += chapter(4, "Invoices", "Be paid on time without being awkward about it.")
    S += [props([("Invoice no.", "Title", "2026-001, 2026-002, and so on"), ("Client", "Relation", "Links to Clients"), ("Project", "Relation", "Links to Projects"), ("Amount", "Number", "Total including tax"),
                 ("Sent on", "Date", "The day you sent it"), ("Paid on", "Date", "Leave empty until the money arrives"), ("Status", "Formula", "Draft, Sent, Overdue or Paid, worked out for you")])]
    S += [p("The status formula", H2), p("Create a formula property called Status. It reads the dates and decides, so you never update it by hand.")]
    S += [code(["if(prop(\"Paid on\") != empty(), \"Paid\",", "  if(prop(\"Sent on\") == empty(), \"Draft\",", "    if(dateBetween(now(), prop(\"Sent on\"), \"days\") > 14, \"Overdue\", \"Sent\")))"])]
    S += [Spacer(1, 6), p("Add a table view filtered to <b>Status is Overdue</b> and pin it to your sidebar. That view is your collections list. On a quiet Friday, work through it from the oldest down.")]
    S += [callout("Payment terms that get paid", "State the due date on the invoice itself, in plain words: \"Due on 14 March.\" Offer one easy way to pay, and send a reminder the day after the due date, not three weeks later.")]
    S += [PageBreak()]

    # 5 tasks
    S += chapter(5, "Tasks", "Small steps that move a project forward.")
    S += [props([("Task", "Title", "Start with a verb: Send, Draft, Call"), ("Project", "Relation", "Links to Projects"), ("When", "Select", "Today, This week, Later, Waiting"), ("Due", "Date", "Only when it is a real deadline"),
                 ("Done", "Checkbox", "Tick to archive from your daily view")])]
    S += [p("Your daily view", H2), p("Create a table named <b>Today</b>, filtered to When is Today and Done is unchecked. Open it each morning. If it has more than five rows, you are planning a fantasy, not a day.")]
    S += [p("The Waiting column", H2), p("Anything that depends on a client goes under <b>Waiting</b>, with the date you asked. On Friday you read that list and nudge. It is the single best habit in this kit for keeping projects moving.")]
    S += [Spacer(1, 8), callout("Rule of three", "Pick at most three tasks that would make today a success. Everything else is a bonus.")]
    S += [PageBreak()]

    # 6 review
    S += chapter(6, "The Friday review", "Fifteen minutes. Every week. It is what makes the rest work.")
    S += [p("Set a recurring reminder for Friday at 4 pm. Make a template button in Studio named <b>Weekly review</b> that creates a new note with the list below, then tick the boxes.", BODY)]
    S += [Check(t) for t in ["Clear the <b>Review</b> stage: send the work or move it back to Draft.", "Open <b>Follow up this week</b> and write every message, then move each date forward.",
                             "Open <b>Overdue</b> invoices and send a polite reminder to each client.", "Mark everything that was paid this week with its Paid on date.",
                             "Empty the <b>Waiting</b> list: nudge anyone who has had it for more than three days.", "Choose the three tasks for Monday and set When to Today.", "Write three lines: what went well, what was hard, what to change."]]
    S += [Spacer(1, 12), p("The monthly check", H2)] + [Check(t) for t in ["Total billed this month and total still unpaid.", "Which client took more time than their fee deserved?", "Archive finished projects, past clients and old notes.", "Raise your price for the next new client by ten percent."]]
    S += [PageBreak()]

    # 7 templates
    S += chapter(7, "Copy-paste templates", "Four messages you will send again and again. Change the brackets and send.")
    S += [KeepTogether([p("Proposal", H2), code(["Hi [name],", "", "Thanks for the call. Here is what I understood: [goal in one sentence].", "I suggest [deliverables], finished by [date], for [fee].", "That includes [rounds] rounds of feedback. [Anything else] is quoted separately.", "If that works, reply \"go\" and I will send the invoice for the deposit.", "", "[Your name]"])])]
    S += [Spacer(1, 0), KeepTogether([p("Project kick-off", H2), code(["Hi [name],", "", "We start on [date]. To begin I need: [files, access, decisions].", "You will see a first draft on [date]. Please send feedback within [3] days.", "The best way to reach me is [channel]. I reply within one working day.", "", "[Your name]"])])]
    S += [Spacer(1, 0), KeepTogether([p("Invoice reminder", H2), code(["Hi [name],", "", "A quick note: invoice [number] for [amount] was due on [date].", "Here is the link to pay: [link]. If it has crossed in the post, ignore this.", "", "Thank you, [Your name]"])])]
    S += [Spacer(1, 0), KeepTogether([p("Project wrap-up", H2), code(["Hi [name],", "", "That is everything delivered: [list]. I will keep the files for [6 months].", "If you are happy, a two-line testimonial would mean a lot. And if you have", "another project in mind, I have room from [date].", "", "[Your name]"])])]
    S += [PageBreak()]

    # 8 formulas
    S += chapter(8, "Formula cheat sheet", "Nine formulas, each one line. Paste them into formula properties.")
    rows = [("Days since sent", 'dateBetween(now(), prop("Sent on"), "days")'), ("Is overdue", 'prop("Status") == "Overdue"'), ("Left to bill", 'prop("Fee") - prop("Invoiced")'),
            ("Days until due", 'dateBetween(prop("Due"), now(), "days")'), ("Due soon flag", 'if(dateBetween(prop("Due"), now(), "days") < 4, "Soon", "")'),
            ("Late fee (5 percent)", 'if(prop("Status") == "Overdue", prop("Amount") * 0.05, 0)'), ("Client label", 'prop("Name") + " (" + prop("Status") + ")"'),
            ("Paid percentage", 'round(prop("Invoiced") / prop("Fee") * 100)'), ("This month", 'formatDate(prop("Sent on"), "MMM YYYY") == formatDate(now(), "MMM YYYY")')]
    data = [[Paragraph("<b>Formula</b>", CELLB), Paragraph("<b>Paste this</b>", CELLB)]] + [[Paragraph(a, CELLB), Paragraph("<font name='Courier' size='8.4'>%s</font>" % b.replace("&", "&amp;").replace("<", "&lt;"), CELL)] for a, b in rows]
    t = Table(data, colWidths=[1.7 * inch, W - 2 * M - 1.7 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(TINT)), ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    S += [t, Spacer(1, 12), callout("If a formula shows an error", "Check that the property names match yours exactly, including capital letters. Notion formulas treat \"Sent on\" and \"sent on\" as different names.")]
    S += [PageBreak()]

    # 9 faq
    S += chapter(9, "Questions and mistakes", "The things people get stuck on, and the quick fix for each.")
    faq = [("Do I need a paid Notion plan?", "No. Everything here works on the free plan. Pay only when you need to share a workspace with a team."),
           ("I have forty clients. Is that too many rows?", "No. Notion handles thousands of rows. Archive past clients to a view called Past so the main list stays short."),
           ("Should I track my time?", "Only if you bill by the hour. Add a Hours number property to Tasks and a Rollup on Projects. Otherwise skip it; fixed fees are easier to manage."),
           ("My relations are a mess.", "Open one database, find rows with an empty relation, and fix them with a filtered view named Missing client. It takes five minutes."),
           ("How do I share with a client?", "Share one project page, not the workspace. Duplicate your project template so they only see what is theirs."),
           ("What if I fall off the habit?", "Do the Friday review once, badly. A messy review still beats none. Restart with the smallest list: overdue invoices and the Waiting column.")]
    for q, a in faq:
        S += [KeepTogether([p("<b>%s</b>" % q, BODY), p(a, ParagraphStyle("a", parent=BODY, textColor=colors.HexColor(MUTED), leftIndent=0))])]
    S += [Spacer(1, 10), callout("The short version", "Five databases. Relations, not copies. A next step on every row. A Friday review. That is the entire system.")]
    S += [Spacer(1, 16), p("Thank you for buying the Notion Freelancer Starter Kit. Questions about your order go to the shop's assistant on your confirmation page.", SMALL)]
    if sample:
        S = S[:cut[0]] + chapter("", "Keep reading", "This is the free sample: the cover, the contents and the first chapter.") + [
            callout("The full kit has eleven pages", "Chapters on Clients, Projects, Invoices (with an overdue formula), Tasks, the Friday review, four copy-paste message templates, nine formulas and a questions page. Buy it from the shop for 29.00 USD.")]
    doc.build(S)


if __name__ == "__main__":
    build("products/notion-freelancer-starter-kit.pdf")
    build("products/notion-freelancer-starter-kit-sample.pdf", sample=True)
