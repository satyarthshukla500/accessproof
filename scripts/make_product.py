"""Builds the sample digital product (a short PDF guide)."""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

PAGES = [
    ("Welcome", "This starter kit shows a freelancer how to set up a small Notion workspace for clients, projects and invoices. Each chapter is one page you can finish in ten minutes."),
    ("1. Clients database", "Create a database with these properties: Name, Email, Status (Lead, Active, Past), Next follow up (date), Notes. Add a board view grouped by Status."),
    ("2. Projects database", "Properties: Project, Client (relation), Due date, Fee, Stage (Brief, Draft, Review, Done). Add a calendar view on Due date and a table view filtered to Stage is not Done."),
    ("3. Invoice tracker", "Properties: Invoice number, Client (relation), Amount, Sent on, Paid on, Status. Use a formula property to flag invoices sent more than 14 days ago and not paid."),
    ("4. Weekly review", "Every Friday: clear the Review stage, send follow ups to Leads, update paid invoices, and write three lines about what went well. Keep the template as a button."),
    ("5. Next steps", "Duplicate the databases for a new client, share one page with them, and keep the rest private. Revisit the setup every quarter and delete what you do not use."),
]
s = getSampleStyleSheet()
doc = SimpleDocTemplate("products/notion-freelancer-starter-kit.pdf", pagesize=letter, title="Notion Freelancer Starter Kit")
out = [Paragraph("Notion Freelancer Starter Kit", s["Title"]), Spacer(1, 12)]
for i, (h, t) in enumerate(PAGES):
    out += [Paragraph(h, s["Heading1"]), Paragraph(t, s["BodyText"])]
    if i < len(PAGES) - 1:
        out.append(PageBreak())
doc.build(out)
