"""Draws static/cover.png, the book cover shown on the store page."""
from PIL import Image, ImageDraw, ImageFont

W, H = 600, 800
img = Image.new("RGB", (W, H), "#0B1B33")
px = img.load()
for y in range(H):  # soft teal wash from the top right
    for x in range(W):
        t = max(0.0, 1 - ((W - x) ** 2 + y ** 2) ** 0.5 / 640)
        r, g, b = px[x, y]
        px[x, y] = (int(r + (45 - r) * t * .35), int(g + (212 - g) * t * .35), int(b + (191 - b) * t * .35))
d = ImageDraw.Draw(img)


def font(size, bold=True):
    for name in ("segoeuib.ttf" if bold else "segoeui.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


d.text((56, 64), "STARTER KIT", font=font(26), fill="#2DD4BF")
for i, line in enumerate(("Notion", "Freelancer", "Starter Kit")):
    d.text((52, 130 + i * 92), line, font=font(78), fill="white")
d.text((56, 440), "Clients, projects and invoices", font=font(28, False), fill="#B7C3D6")
d.text((56, 480), "in one calm workspace.", font=font(28, False), fill="#B7C3D6")
for i in range(3):  # three linked blocks, the product's motif
    x = 56 + i * 150
    d.rounded_rectangle((x, 610, x + 110, 690), radius=22, outline="#2DD4BF", width=5, fill="#2DD4BF" if i == 2 else "#0B1B33")
    if i < 2:
        d.line((x + 110, 650, x + 150, 650), fill="#2DD4BF", width=5)
img.save("static/cover.png", optimize=True)
