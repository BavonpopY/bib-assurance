"""BIB Assurance - minimalist corporate SVG set (deep navy, white, slate, gold).

Usage: python make_svgs_v2.py <out_dir>
Writes:  images/  (logo, favicon, hero, about, states)  -> catalog/static/images/
         product/ (5 plan illustrations)                 -> media/product/
         avatar/  (initials avatars)                      -> media/avatar/
         claim/   (supporting documents & imaging)        -> media/claim/
         application/ (underwriting documents: ID, occupation)  -> media/application/
"""
import math
import os
import random
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"

NAVY = "#0A1D37"
NAVY2 = "#0F294A"
NAVY3 = "#1E3A5F"
SLATE = "#64748B"
SLATE2 = "#94A3B8"
LINE = "#CBD5E1"
MIST = "#E2E8F0"
PALE = "#F1F5F9"
BG = "#F8FAFC"
WHITE = "#FFFFFF"
GOLD = "#B8975A"
GOLD2 = "#D8C49B"
GOLD3 = "#F3EBDC"
FONT = "Georgia, 'Times New Roman', serif"
SANS = "'Segoe UI', Helvetica, Arial, sans-serif"


def w(path, content):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def svg(width, height, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')


def g(body, stroke=NAVY2, sw=3, fill="none", extra=""):
    return (f'<g fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round"{extra}>{body}</g>')


def rect(x, y, wd, ht, rx=0, fill="none", stroke=None, sw=None):
    s = f' stroke="{stroke}"' if stroke else ""
    s += f' stroke-width="{sw}"' if sw is not None else ""
    return f'<rect x="{x}" y="{y}" width="{wd}" height="{ht}" rx="{rx}" fill="{fill}"{s}/>'


def circle(cx, cy, r, fill="none", stroke=None, sw=None):
    s = f' stroke="{stroke}"' if stroke else ""
    s += f' stroke-width="{sw}"' if sw is not None else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{s}/>'


def path(d, fill="none", stroke=None, sw=None, extra=""):
    s = f' stroke="{stroke}"' if stroke else ""
    s += f' stroke-width="{sw}"' if sw is not None else ""
    return f'<path d="{d}" fill="{fill}"{s}{extra}/>'


def line(x1, y1, x2, y2, stroke=None, sw=None):
    s = f' stroke="{stroke}"' if stroke else ""
    s += f' stroke-width="{sw}"' if sw is not None else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"{s}/>'


def text(x, y, t, size=16, fill=NAVY, weight=600, anchor="middle", family=SANS, ls=0):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}" stroke="none">{t}</text>')


SHIELD = "M {cx} {t} L {r} {t2} L {r} {m} C {r} {b1} {cx2} {b2} {cx} {b} C {cx3} {b2} {l} {b1} {l} {m} L {l} {t2} Z"


def shield_path(cx, top, wd, ht):
    l, r = cx - wd / 2, cx + wd / 2
    return SHIELD.format(cx=cx, t=top, r=r, t2=top + ht * 0.14, m=top + ht * 0.5, b1=top + ht * 0.78,
                         cx2=cx + wd * 0.22, b2=top + ht * 0.93, b=top + ht, cx3=cx - wd * 0.22, l=l)


# ---------------------------------------------------------------- brand
def logo():
    s = path(shield_path(60, 6, 96, 118), fill=NAVY2)
    s += path(shield_path(60, 14, 80, 100), stroke=GOLD, sw=2)
    s += text(60, 76, "BIB", 28, WHITE, 700, family=FONT, ls=1)
    w("images/bib_logo.svg", svg(120, 130, s, "BIB Assurance"))
    w("images/favicon.svg", svg(120, 130, s, "BIB Assurance"))
    # horizontal wordmark (for documents / README)
    s2 = path(shield_path(40, 6, 64, 80), fill=NAVY2) + path(shield_path(40, 12, 52, 66), stroke=GOLD, sw=1.5)
    s2 += text(40, 52, "BIB", 18, WHITE, 700, family=FONT)
    s2 += text(88, 44, "BIB Assurance", 30, NAVY, 700, anchor="start", family=FONT)
    s2 += text(90, 68, "TRUSTED PROTECTION FOR EVERY STAGE OF LIFE", 10.5, GOLD, 600, anchor="start", ls=1.6)
    w("images/bib_wordmark.svg", svg(470, 92, s2, "BIB Assurance"))


def family(cx, base, scale=1.0, color=NAVY2, sw=3):
    """Three line-art figures (two adults, one child)."""
    out = ""
    for dx, sz in ((-46, 1.0), (46, 0.95), (0, 0.62)):
        x = cx + dx * scale
        hr = 17 * sz * scale
        body_h = 70 * sz * scale
        top = base - body_h - hr * 2 - 6 * scale
        out += circle(x, top + hr, hr)
        out += path(f"M {x - 26 * sz * scale} {base} L {x - 26 * sz * scale} {base - body_h + 22 * sz * scale} "
                    f"Q {x - 26 * sz * scale} {base - body_h} {x} {base - body_h} "
                    f"Q {x + 26 * sz * scale} {base - body_h} {x + 26 * sz * scale} {base - body_h + 22 * sz * scale} "
                    f"L {x + 26 * sz * scale} {base}")
    return g(out, stroke=color, sw=sw)


def hero():
    W, H = 900, 700
    s = rect(0, 0, W, H, 28, PALE)
    s += circle(640, 210, 190, MIST)
    s += circle(250, 520, 140, GOLD3)
    # skyline line-art
    sky = ""
    xs = [(60, 380), (130, 300), (210, 420), (300, 340), (600, 360), (680, 260), (770, 330)]
    for x, top in xs:
        sky += rect(x, top, 70, 560 - top, 2)
        for wy in range(top + 24, 540, 38):
            sky += line(x + 18, wy, x + 52, wy)
    s += g(sky, stroke=LINE, sw=2)
    s += line(40, 560, 860, 560, LINE, 3)
    # shield
    s += path(shield_path(450, 120, 330, 400), fill=WHITE, stroke=NAVY2, sw=6)
    s += path(shield_path(450, 142, 290, 352), stroke=GOLD, sw=2.5)
    s += family(450, 455, 1.35, NAVY2, 4)
    # heartbeat line
    s += path("M 120 610 L 330 610 L 352 572 L 378 650 L 402 594 L 420 610 L 780 610", stroke=GOLD, sw=4,
              extra=' stroke-linecap="round" stroke-linejoin="round"')
    # small badges
    s += circle(735, 470, 46, NAVY2) + g(path("M 714 470 L 730 486 L 758 456"), stroke=WHITE, sw=6)
    s += circle(170, 250, 36, WHITE, LINE, 2) + g(path("M 170 232 L 170 268 M 152 250 L 188 250"), stroke=GOLD, sw=6)
    w("images/hero.svg", svg(W, H, s, "Family protected by BIB Assurance"))


def about():
    W, H = 900, 600
    s = rect(0, 0, W, H, 28, PALE) + circle(700, 160, 150, MIST)
    b = ""
    b += path("M 230 210 L 450 110 L 670 210 Z")
    b += rect(250, 210, 400, 26, 2)
    for i in range(6):
        x = 280 + i * 66
        b += rect(x, 252, 26, 210, 2)
    b += rect(230, 462, 440, 26, 2) + rect(205, 488, 490, 26, 2)
    s += g(b, stroke=NAVY2, sw=5)
    s += circle(450, 168, 18, GOLD)
    s += line(120, 514, 780, 514, LINE, 3)
    w("images/about.svg", svg(W, H, s, "BIB Assurance head office"))


def state_images():
    s = circle(100, 100, 92, MIST) + circle(100, 82, 34, SLATE2) + path("M 38 168 Q 100 104 162 168 A 92 92 0 0 1 38 168 Z", fill=SLATE2)
    w("images/default_avatar.svg", svg(200, 200, s, "Profile"))

    s = rect(0, 0, 320, 220, 20, PALE)
    s += g(path("M 90 70 L 140 70 L 155 86 L 230 86 L 230 170 L 90 170 Z"), stroke=SLATE2, sw=4)
    s += circle(212, 150, 22, PALE, SLATE, 4) + line(228, 166, 246, 184, SLATE, 5)
    w("images/empty_state.svg", svg(320, 220, s, "Nothing to show yet"))

    s = rect(0, 0, 320, 260, 20, PALE) + circle(160, 130, 96, WHITE, LINE, 2)
    s += path(shield_path(160, 52, 120, 150), fill=NAVY2) + path(shield_path(160, 62, 100, 128), stroke=GOLD, sw=2)
    s += g(path("M 130 128 L 152 150 L 192 108"), stroke=WHITE, sw=9)
    w("images/policy_issued.svg", svg(320, 260, s, "Policy issued"))

    s = rect(0, 0, 320, 220, 20, PALE)
    s += rect(70, 60, 180, 112, 14, WHITE, NAVY2, 4) + rect(70, 86, 180, 22, 0, NAVY2)
    s += rect(88, 128, 40, 26, 4, GOLD3, GOLD, 2)
    s += circle(236, 158, 30, WHITE, "#B42318", 4) + g(path("M 224 146 L 248 170 M 248 146 L 224 170"), stroke="#B42318", sw=5)
    w("images/payment_declined.svg", svg(320, 220, s, "Payment not completed"))


# ---------------------------------------------------------------- products (600 x 400)
def product_frame(body, title):
    s = rect(0, 0, 600, 400, 0, PALE)
    s += circle(470, 90, 150, MIST) + circle(110, 360, 110, GOLD3)
    s += body
    return svg(600, 400, s, title)


def heart(cx, cy, size):
    k = size
    return (f"M {cx} {cy + k * 0.9} C {cx - k * 1.6} {cy - k * 0.1} {cx - k * 0.9} {cy - k * 1.25} {cx} {cy - k * 0.45} "
            f"C {cx + k * 0.9} {cy - k * 1.25} {cx + k * 1.6} {cy - k * 0.1} {cx} {cy + k * 0.9} Z")


def products():
    # 1 Health Happy: heart + medical cross + pulse
    b = path(heart(300, 200, 120), fill=WHITE, stroke=NAVY2, sw=6)
    b += rect(278, 128, 44, 120, 6, GOLD) + rect(240, 166, 120, 44, 6, GOLD)
    b += path("M 70 330 L 210 330 L 232 296 L 256 360 L 280 318 L 296 330 L 530 330", stroke=NAVY2, sw=4,
              extra=' stroke-linecap="round" stroke-linejoin="round"')
    w("product/bib_health_happy.svg", product_frame(b, "BIB Health Happy"))

    # 2 CI Super Care: shield + heart + ECG + award ribbon
    b = path(shield_path(300, 60, 220, 270), fill=WHITE, stroke=NAVY2, sw=6)
    b += path(heart(300, 190, 62), fill=GOLD3, stroke=GOLD, sw=4)
    b += path("M 214 196 L 262 196 L 278 168 L 298 226 L 316 182 L 330 196 L 386 196", stroke=NAVY2, sw=4,
              extra=' stroke-linecap="round" stroke-linejoin="round"')
    b += circle(452, 290, 34, NAVY2) + path("M 434 318 L 426 366 L 452 352 L 478 366 L 470 318", fill=NAVY2)
    b += circle(452, 290, 18, "none", GOLD, 3)
    w("product/bib_ci_super_care.svg", product_frame(b, "BIB CI Super Care"))

    # 3 Life Protector: house roof + family
    b = g(path("M 160 200 L 300 92 L 440 200") + path("M 186 186 L 186 330 L 414 330 L 414 186"), stroke=NAVY2, sw=6)
    b += family(300, 318, 1.0, NAVY2, 4)
    b += path("M 380 116 L 380 72 L 408 72 L 408 140", stroke=NAVY2, sw=5, extra=' stroke-linejoin="round"')
    b += circle(300, 70, 10, GOLD)
    b += line(120, 330, 480, 330, GOLD, 4)
    w("product/bib_life_protector.svg", product_frame(b, "BIB Life Protector"))

    # 4 PA Shield: shield + walking figure + plaster
    b = path(shield_path(300, 52, 230, 290), fill=WHITE, stroke=NAVY2, sw=6)
    fig = circle(296, 116, 18)
    fig += path("M 296 136 L 290 210 M 290 210 L 262 270 M 290 210 L 322 268 M 292 160 L 260 196 M 292 160 L 334 182")
    b += g(fig, stroke=NAVY2, sw=6)
    b += rect(430, 250, 86, 34, 17, GOLD3, GOLD, 3) + circle(462, 267, 3, GOLD) + circle(484, 267, 3, GOLD)
    w("product/bib_pa_shield.svg", product_frame(b, "BIB PA Shield"))

    # 5 Smart Retire: horizon sun + rising bars + coins
    b = path("M 170 270 A 130 130 0 0 1 430 270", fill=GOLD3, stroke=GOLD, sw=4)
    for i in range(7):
        a = math.radians(200 + i * 23.3)
        b += line(300 + math.cos(a) * 150, 270 + math.sin(a) * 150, 300 + math.cos(a) * 172, 270 + math.sin(a) * 172, GOLD, 4)
    for i, h in enumerate((40, 70, 105, 145)):
        b += rect(196 + i * 56, 300 - h, 36, h, 4, WHITE, NAVY2, 4)
    b += line(120, 300, 480, 300, NAVY2, 5)
    for i in range(4):
        b += path(f"M 430 {330 - i * 14} a 34 10 0 0 0 68 0 a 34 10 0 0 0 -68 0 Z", fill=WHITE, stroke=NAVY2, sw=3)
    b += path("M 196 236 L 252 200 L 308 176 L 364 132", stroke=GOLD, sw=4) + circle(364, 132, 7, GOLD)
    w("product/bib_smart_retire.svg", product_frame(b, "BIB Smart Retire"))


# ---------------------------------------------------------------- avatars (initials)
def avatars(people):
    for slug, initials, tone in people:
        bg = {0: NAVY2, 1: NAVY3, 2: "#334155"}[tone]
        s = circle(100, 100, 96, bg) + circle(100, 100, 88, "none", GOLD, 2.5)
        s += text(100, 116, initials, 50, WHITE, 600, family=FONT, ls=1)
        w(f"avatar/{slug}.svg", svg(200, 200, s, initials))


# ---------------------------------------------------------------- claim documents (640 x 480)
def doc_frame(title, body, stamp=None):
    s = rect(0, 0, 640, 480, 0, MIST)
    s += rect(150, 26, 340, 430, 6, WHITE, LINE, 2)
    s += rect(150, 26, 340, 56, 6, NAVY2) + rect(150, 70, 340, 12, 0, NAVY2)
    s += circle(182, 54, 14, "none", GOLD, 2.5) + path("M 176 54 L 182 48 L 188 54 L 182 60 Z", fill=GOLD)
    s += text(204, 60, title, 15, WHITE, 700, anchor="start", ls=1.2)
    s += body
    if stamp:
        s += f'<g transform="rotate(-14 418 386)">{circle(418, 386, 40, "none", GOLD, 3)}{circle(418, 386, 33, "none", GOLD, 1.5)}' \
             f'{text(418, 391, stamp, 13, GOLD, 800, ls=1.5)}</g>'
    s += path("M 186 420 C 206 396 222 432 240 410 C 254 394 262 426 284 412", stroke=NAVY2, sw=2.5)
    s += line(180, 432, 300, 432, LINE, 1.5)
    return s


def bars(x, y, widths, gap=20, color=LINE, h=8):
    return "".join(rect(x, y + i * gap, wd, h, 4, color) for i, wd in enumerate(widths))


def doc_text_block(rows=(250, 230, 270, 180), y=110):
    return bars(180, y, rows)


def imaging_frame(title, body):
    s = rect(0, 0, 640, 480, 0, MIST)
    s += rect(110, 30, 420, 420, 10, NAVY, NAVY2, 4)
    s += text(130, 60, title, 13, SLATE2, 600, anchor="start", ls=1.5)
    s += text(510, 60, "R", 16, SLATE2, 700, anchor="end")
    s += body
    return s


def documents():
    # hospital invoice
    b = doc_text_block((200, 150), 104)
    b += rect(180, 160, 280, 26, 3, PALE)
    for i in range(6):
        y = 196 + i * 26
        b += rect(186, y, 150 - (i * 13) % 50, 8, 4, LINE) + rect(400, y, 52, 8, 4, SLATE2)
    b += line(180, 362, 460, 362, NAVY2, 2) + rect(186, 372, 90, 10, 5, NAVY2) + rect(388, 372, 64, 10, 5, NAVY2)
    w("claim/hospital_invoice.svg", svg(640, 480, doc_frame("HOSPITAL INVOICE", b, "PAID"), "Hospital invoice"))

    b = doc_text_block((180, 120), 104) + bars(180, 168, (280, 260, 270, 240, 200, 250, 160))
    w("claim/medical_certificate.svg", svg(640, 480, doc_frame("MEDICAL CERTIFICATE", b, "CERTIFIED"), "Medical certificate"))

    b = doc_text_block((210, 140), 104)
    b += text(180, 168, "DIAGNOSIS", 10, SLATE, 700, anchor="start", ls=1) + bars(180, 176, (270, 210))
    b += text(180, 238, "TREATMENT", 10, SLATE, 700, anchor="start", ls=1) + bars(180, 246, (260, 280, 190))
    b += text(180, 328, "DISCHARGE", 10, SLATE, 700, anchor="start", ls=1) + bars(180, 336, (230,))
    w("claim/discharge_summary.svg", svg(640, 480, doc_frame("DISCHARGE SUMMARY", b, "VERIFIED"), "Discharge summary"))

    b = doc_text_block((190, 130), 104)
    for i in range(7):
        y = 170 + i * 24
        b += rect(186, y, 110, 8, 4, LINE) + rect(330, y, 40, 8, 4, SLATE2) + rect(392, y, 56, 8, 4, LINE)
        if i in (2, 5):
            b += circle(458, y + 4, 4, GOLD)
    w("claim/lab_report.svg", svg(640, 480, doc_frame("LABORATORY REPORT", b), "Laboratory report"))

    b = doc_text_block((200, 160), 104)
    b += rect(180, 170, 280, 110, 6, PALE, LINE, 1.5)
    for i in range(5):
        b += path(f"M {196 + i * 52} {268 - i * 7} q 12 -40 24 -6 q 10 -26 22 -14", stroke=SLATE2, sw=2)
    b += bars(180, 300, (260, 220, 240))
    w("claim/pathology_report.svg", svg(640, 480, doc_frame("PATHOLOGY REPORT", b, "REVIEWED"), "Pathology report"))

    b = doc_text_block((210, 150), 104)
    grid = "".join(line(180 + i * 20, 170, 180 + i * 20, 330, "#F3D6D2", 1) for i in range(15))
    grid += "".join(line(180, 170 + i * 20, 460, 170 + i * 20, "#F3D6D2", 1) for i in range(9))
    b += grid
    ecg = "M 180 250"
    for k in range(4):
        x0 = 180 + k * 70
        ecg += f" L {x0 + 20} 250 L {x0 + 26} 242 L {x0 + 32} 250 L {x0 + 38} 250 L {x0 + 42} 206 L {x0 + 47} 276 L {x0 + 52} 250 L {x0 + 70} 250"
    b += path(ecg, stroke=NAVY2, sw=2.5, extra=' stroke-linejoin="round"')
    b += bars(180, 350, (250, 180))
    w("claim/ecg_report.svg", svg(640, 480, doc_frame("ELECTROCARDIOGRAM", b), "ECG report"))

    b = doc_text_block((200, 140), 104)
    b += text(186, 196, "Rx", 34, NAVY2, 700, anchor="start", family=FONT)
    b += bars(240, 172, (200, 160)) + bars(186, 230, (260, 230, 250, 210, 170))
    w("claim/prescription.svg", svg(640, 480, doc_frame("PRESCRIPTION", b), "Prescription"))

    b = doc_text_block((220, 150), 104)
    b += rect(180, 168, 280, 120, 6, PALE, LINE, 1.5)
    b += path("M 200 270 L 260 200 L 330 230 L 440 180", stroke=LINE, sw=10, extra=' stroke-linecap="round"')
    b += line(320, 168, 320, 288, LINE, 8)
    b += circle(318, 224, 12, "none", GOLD, 3) + line(306, 212, 330, 236, GOLD, 3) + line(330, 212, 306, 236, GOLD, 3)
    b += bars(180, 304, (260, 240, 190))
    w("claim/accident_report.svg", svg(640, 480, doc_frame("ACCIDENT REPORT", b, "FILED"), "Accident report"))

    # imaging
    ribs = ""
    for i in range(6):
        y = 150 + i * 36
        ribs += path(f"M 316 {y} C 280 {y - 6} 230 {y + 6} 200 {y + 40}", stroke=WHITE, sw=5)
        ribs += path(f"M 324 {y} C 360 {y - 6} 410 {y + 6} 440 {y + 40}", stroke=WHITE, sw=5)
    ribs += line(320, 110, 320, 400, WHITE, 10)
    ribs += path("M 200 120 Q 320 70 440 120", stroke=WHITE, sw=6)
    body = f'<g opacity="0.85">{ribs}</g>' + circle(380, 250, 30, "none", GOLD, 3)
    w("claim/xray_chest.svg", svg(640, 480, imaging_frame("CHEST PA", body), "Chest X-ray"))

    bone = path("M 220 140 C 236 124 262 134 262 154 L 330 300 C 350 290 372 304 366 326 C 362 344 340 350 326 340 "
                "L 252 192 C 232 200 210 176 220 140 Z", fill=WHITE, extra=' opacity="0.85"')
    bone += path("M 352 120 C 368 104 394 116 392 136 L 410 330 C 430 330 440 352 426 368 C 412 380 392 374 388 358 "
                 "L 368 160 C 346 160 336 136 352 120 Z", fill=WHITE, extra=' opacity="0.85"')
    bone += path("M 280 226 L 300 222 L 292 236 L 312 232", stroke="#E57B6E", sw=3)
    bone += circle(296, 230, 32, "none", GOLD, 3)
    w("claim/xray_wrist.svg", svg(640, 480, imaging_frame("FOREARM AP", bone), "Forearm X-ray"))

    brain = circle(320, 250, 140, "#2B3E5C") + circle(320, 250, 118, "#3A5172")
    brain += path("M 230 220 q 30 -40 60 -10 q 30 -40 60 0 q 30 -30 50 10 M 220 280 q 40 30 70 0 q 30 30 60 0 q 30 30 60 -6",
                  stroke=SLATE2, sw=4)
    brain += line(320, 132, 320, 368, "#2B3E5C", 4) + circle(362, 214, 22, "none", GOLD, 3)
    w("claim/mri_brain.svg", svg(640, 480, imaging_frame("MRI AXIAL T2", brain), "MRI scan"))

    knee = path("M 260 110 L 300 110 L 304 230 Q 320 250 336 230 L 340 110 L 380 110 L 372 240 Q 320 300 268 240 Z",
                fill=WHITE, extra=' opacity="0.8"')
    knee += path("M 268 270 Q 320 310 372 270 L 366 400 L 326 400 L 322 300 L 318 300 L 314 400 L 274 400 Z",
                 fill=WHITE, extra=' opacity="0.8"')
    knee += circle(320, 262, 26, "none", GOLD, 3)
    w("claim/mri_knee.svg", svg(640, 480, imaging_frame("MRI KNEE SAG", knee), "Knee MRI"))


def application_documents():
    # copy of an ID card (specimen - no real numbers)
    s = rect(0, 0, 640, 480, 0, MIST)
    s += rect(110, 90, 420, 270, 18, WHITE, LINE, 2)
    s += rect(110, 90, 420, 52, 18, NAVY2) + rect(110, 124, 420, 18, 0, NAVY2)
    s += circle(142, 116, 13, "none", GOLD, 2.5)
    s += text(166, 122, "IDENTITY CARD", 15, WHITE, 700, anchor="start", ls=1.5)
    s += rect(136, 164, 110, 136, 8, PALE, LINE, 1.5)
    s += circle(191, 214, 26, MIST, SLATE2, 2) + path("M 151 296 C 156 252 226 252 231 296", fill=MIST, stroke=SLATE2, sw=2)
    s += bars(270, 168, (200, 150, 230, 120, 180), gap=24)
    s += rect(270, 300, 230, 22, 4, PALE) + bars(278, 307, (160,), h=8, color=SLATE2)
    s += f'<g transform="rotate(-12 420 260)">{rect(345, 238, 150, 40, 6, "none", GOLD, 3)}' \
         f'{text(420, 265, "COPY ONLY", 16, GOLD, 800, ls=2)}</g>'
    w("application/id_card_copy.svg", svg(640, 480, s, "Copy of ID card"))

    b = doc_text_block((210, 160), 104) + bars(180, 168, (280, 250, 270, 230, 260, 190))
    b += text(180, 318, "POSITION", 10, SLATE, 700, anchor="start", ls=1) + bars(180, 326, (180,), color=SLATE2)
    w("application/employment_certificate.svg",
      svg(640, 480, doc_frame("EMPLOYMENT CERTIFICATE", b, "VERIFIED"), "Employment certificate"))

    b = doc_text_block((190, 140), 104) + rect(180, 160, 280, 24, 3, PALE)
    for i in range(5):
        y = 194 + i * 26
        b += rect(186, y, 130 - (i * 17) % 40, 8, 4, LINE) + rect(404, y, 48, 8, 4, SLATE2)
    b += line(180, 330, 460, 330, NAVY2, 2) + text(186, 352, "NET PAY", 11, NAVY2, 700, anchor="start", ls=1)
    b += rect(392, 342, 60, 10, 5, NAVY2)
    w("application/salary_slip.svg", svg(640, 480, doc_frame("SALARY SLIP", b), "Salary slip"))

    b = doc_text_block((230, 170), 104) + bars(180, 168, (270, 240, 260))
    b += rect(180, 236, 280, 90, 6, PALE, LINE, 1.5) + bars(196, 252, (200, 170, 220), gap=22)
    w("application/business_registration.svg",
      svg(640, 480, doc_frame("BUSINESS REGISTRATION", b, "OFFICIAL"), "Business registration"))

    b = doc_text_block((200, 150), 104)
    for i, (lab, wd) in enumerate((("BMI", 90), ("BLOOD PRESSURE", 120), ("GLUCOSE", 70), ("CHOLESTEROL", 110))):
        y = 172 + i * 34
        b += text(180, y + 8, lab, 10, SLATE, 700, anchor="start", ls=1) + rect(330, y, wd, 10, 5, NAVY3)
    b += bars(180, 316, (260, 200))
    w("application/health_checkup.svg",
      svg(640, 480, doc_frame("HEALTH CHECK-UP", b, "NORMAL"), "Health check-up report"))


PEOPLE = [
    ("siriporn_saetang", "SS", 0), ("pimchanok_wongsa", "PW", 1), ("krit_chaiyaporn", "KC", 2),
    ("mintra_suksai", "MS", 0), ("somchai_jaidee", "SJ", 1), ("fah_rattanakul", "FR", 2),
    ("arthit_boonsong", "AB", 0), ("chompoo_srisuk", "CS", 1), ("daniel_carter", "DC", 2),
    ("emi_tanaka", "ET", 0), ("gun_phongphan", "GP", 1), ("jenjira_kaewmanee", "JK", 2),
    ("lukas_becker", "LB", 0), ("mali_thongdee", "MT", 1), ("nok_prasert", "NP", 2), ("priya_sharma", "PS", 0),
]

if __name__ == "__main__":
    logo()
    hero()
    about()
    state_images()
    products()
    avatars(PEOPLE)
    documents()
    application_documents()
    n = sum(len(f) for _, _, f in os.walk(OUT))
    print("SVG files:", n)
