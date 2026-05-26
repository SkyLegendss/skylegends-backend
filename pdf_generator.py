from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
import io
import os
from datetime import datetime, timedelta

# ─── Colors ───────────────────────────────────────────────────────────────────
C_DARK    = colors.HexColor("#111111")   # near-black for table headers / text
C_BLUE    = colors.HexColor("#000000")   # primary accent (logo, rule, total box)
C_BLUE_LT = colors.HexColor("#efefef")   # light accent bg (total summary row)
C_GREY    = colors.HexColor("#777777")   # secondary / label text
C_LGREY   = colors.HexColor("#f7f7f7")   # alternating row bg
C_WHITE   = colors.white

PRICE_PER_M2 = 107  # bez DPH
VAT_RATE = 1.21

COMPANY = {
    "name":    "SENTEMOV GROUP s.r.o.",
    "address": "Jiráskova 2860, zelené předměstí, 530 02 Pardubice",
    "ico":     "23089768",
    "dic":     "CZ23089768",
    "email":   "info@skylegends.eu",
    "tel":     "774306718",
}

# ─── Unicode font setup ───────────────────────────────────────────────────────
# Helvetica does not support Czech diacritics or Cyrillic.
# Try common system TTF fonts in order; fall back to Helvetica only if nothing found.

def _setup_fonts():
    import reportlab as _rl
    _rl_fonts = os.path.join(os.path.dirname(_rl.__file__), "fonts")

    candidates = [
        # Windows: Arial — Czech + Cyrillic
        (
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/ariali.ttf",
            "C:/Windows/Fonts/arialbi.ttf",
        ),
        # Linux: DejaVu Sans — Czech + Cyrillic (installed via Dockerfile)
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        ),
        # Linux: Liberation Sans
        (
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
        ),
        # reportlab-bundled Vera — Czech only, no Cyrillic; last resort
        (
            os.path.join(_rl_fonts, "Vera.ttf"),
            os.path.join(_rl_fonts, "VeraBd.ttf"),
            os.path.join(_rl_fonts, "VeraIt.ttf"),
            os.path.join(_rl_fonts, "VeraBI.ttf"),
        ),
    ]
    for reg, bold, ital, bita in candidates:
        if os.path.exists(reg):
            try:
                pdfmetrics.registerFont(TTFont("UF",     reg))
                pdfmetrics.registerFont(TTFont("UF-B",   bold))
                pdfmetrics.registerFont(TTFont("UF-I",   ital))
                pdfmetrics.registerFont(TTFont("UF-BI",  bita))
                registerFontFamily("UF", normal="UF", bold="UF-B",
                                   italic="UF-I", boldItalic="UF-BI")
                return "UF", "UF-B", "UF-I", "UF-BI"
            except Exception:
                continue
    # Helvetica fallback — diacritics will be missing but no crash
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"


F_REG, F_BOLD, F_ITAL, F_BITA = _setup_fonts()

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _st(name, **kw):
    return ParagraphStyle(name, **kw)


def _info_block(title, lines, col_w, S_note):
    rows = [[Paragraph(title, _st(f"pt_{id(title)}", fontName=F_BOLD,
                                  fontSize=7, textColor=C_BLUE, spaceAfter=3))]]
    for label, val in lines:
        if val:
            rows.append([Paragraph(f"<b>{label}</b>  {val}", S_note)])
    return Table(rows, colWidths=[col_w], style=TableStyle([
        ("TOPPADDING",    (0,0), (-1,-1), 1),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1),
        ("BACKGROUND",    (0,0), (0,0),   C_LGREY),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
    ]))


def _kp_header(story, order_num, subtitle, now, validity):
    S_logo  = _st("logo_h",  fontName=F_BOLD, fontSize=22, textColor=C_BLUE)
    S_tag   = _st("tag_h",   fontName=F_REG,  fontSize=8,  textColor=C_GREY, spaceAfter=0)
    S_label = _st("lbl_h",   fontName=F_BOLD, fontSize=7,  textColor=C_GREY,
                  spaceAfter=1, wordWrap="LTR", leading=10)
    S_val   = _st("val_h",   fontName=F_REG,  fontSize=9,  textColor=C_DARK, leading=13)

    ref_num = order_num.replace("AW-", "NB-")
    header_data = [[
        Paragraph("SKY LEGENDS", S_logo),
        "",
        Table([
            [Paragraph("CENOVÁ NABÍDKA", _st("fi_h", fontName=F_BOLD,
                                              fontSize=8, textColor=C_GREY)),
             Paragraph(ref_num, _st("fn_h", fontName=F_BOLD,
                                    fontSize=16, textColor=C_BLUE))],
            [Paragraph("Datum vystavení", S_label),
             Paragraph(now.strftime("%d.%m.%Y"), S_val)],
            [Paragraph("Platnost nabídky", S_label),
             Paragraph(validity.strftime("%d.%m.%Y"), S_val)],
        ], colWidths=[26*mm, 44*mm], style=TableStyle([
            ("ALIGN",         (1,0), (1,-1), "RIGHT"),
            ("TOPPADDING",    (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ])),
    ]]
    # 65 mm for logo (was 55 — too narrow, caused line break)
    ht = Table(header_data, colWidths=[65*mm, None, 72*mm])
    ht.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(ht)
    story.append(Paragraph(subtitle, S_tag))
    story.append(Spacer(1, 3*mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_BLUE, spaceAfter=6*mm))


def _kp_parties(story, W, client, S_note):
    supplier = _info_block("DODAVATEL", [
        ("Firma:",  COMPANY["name"]),
        ("Adresa:", COMPANY["address"]),
        ("IČO:",    COMPANY["ico"]),
        ("DIČ:",    COMPANY["dic"]),
        ("E-mail:", COMPANY["email"]),
        ("Tel:",    COMPANY["tel"]),
    ], (W/2)-5*mm, S_note)

    buyer = _info_block("ODBĚRATEL", [
        ("Jméno:",  client.get("name", "")),
        ("Firma:",  client.get("company", "")),
        ("Adresa:", client.get("billing_address", "")),
        ("IČO:",    client.get("ico", "")),
        ("E-mail:", client.get("email", "")),
        ("Tel:",    client.get("phone", "")),
    ], (W/2)-5*mm, S_note)

    parties = Table([[supplier, "", buyer]], colWidths=[(W/2)-3*mm, 6*mm, (W/2)-3*mm])
    parties.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    story.append(parties)
    story.append(Spacer(1, 7*mm))


def _kp_location(story, W, location, S_val):
    if not location:
        return
    loc_t = Table([[
        Paragraph("Místo provedení služby:", _st("lh_loc", fontName=F_BOLD,
                                                  fontSize=8, textColor=C_GREY)),
        Paragraph(location, S_val),
    ]], colWidths=[52*mm, W-52*mm])
    loc_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_LGREY),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(loc_t)
    story.append(Spacer(1, 6*mm))


def _kp_total_box(story, W, total):
    total_t = Table([
        ["", "CELKOVÁ CENA BEZ DPH:", f"{total:,.0f} Kč"]
    ], colWidths=[W-85*mm, 55*mm, 30*mm])
    total_t.setStyle(TableStyle([
        ("BACKGROUND",    (1,0), (-1,0), C_BLUE),
        ("TEXTCOLOR",     (1,0), (-1,0), C_WHITE),
        ("FONTNAME",      (0,0), (-1,-1), F_BOLD),
        ("FONTSIZE",      (1,0), (1,0),  9),
        ("FONTSIZE",      (2,0), (2,0),  14),
        ("ALIGN",         (1,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (1,0), (-1,-1), 8),
        ("RIGHTPADDING",  (1,0), (-1,-1), 8),
    ]))
    story.append(total_t)


def _kp_conditions(story, W, order, validity, S_note):
    cond_data = [
        [
            Paragraph("PODMÍNKY NABÍDKY", _st("ph_c", fontName=F_BOLD,
                                               fontSize=7, textColor=C_GREY)),
            Paragraph("TERMÍN PROVEDENÍ", _st("ph2_c", fontName=F_BOLD,
                                               fontSize=7, textColor=C_GREY)),
        ],
        [
            Paragraph(
                f"Platnost nabídky: <b>{validity.strftime('%d.%m.%Y')}</b><br/>"
                "Ceny jsou uvedeny bez DPH.<br/>"
                "DPH bude účtováno dle platných předpisů.",
                S_note
            ),
            Paragraph(
                (f"Požadovaný termín: <b>{order.get('service_date', '—')}</b><br/>"
                 if order.get("service_date") else "Termín: <b>Dle dohody</b><br/>") +
                "Typ objektu: <b>" + order.get("building_type", "—") + "</b><br/>" +
                (f"Počet podlaží: <b>{order.get('floors', '—')}</b>"
                 if order.get("floors") else ""),
                S_note
            ),
        ],
    ]
    cond_t = Table(cond_data, colWidths=[(W/2)-3*mm, (W/2)-3*mm],
                   style=TableStyle([
        ("BACKGROUND",   (0,0), (-1,0),  C_LGREY),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.HexColor("#e0e0e0")),
        ("LINEBETWEEN",  (0,0), (1,-1),  0.5, colors.HexColor("#e0e0e0")),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ]))
    story.append(cond_t)


def _kp_footer(story, now):
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#e0e0e0"), spaceAfter=3*mm))
    story.append(Paragraph(
        f"{COMPANY['name']}  ·  {COMPANY['address']}  ·  IČO: {COMPANY['ico']}  ·  "
        f"{COMPANY['email']}  ·  {COMPANY['tel']}",
        _st("ft_f", fontName=F_REG, fontSize=7, textColor=C_GREY, alignment=1)
    ))
    story.append(Paragraph(
        f"Dokument vygenerován automaticky dne {now.strftime('%d.%m.%Y %H:%M')}",
        _st("ft2_f", fontName=F_REG, fontSize=6,
            textColor=colors.HexColor("#aaaaaa"), alignment=1, spaceBefore=2)
    ))


# ─── KP1: Mytí fasád a oken drony ─────────────────────────────────────────────

def generate_invoice_pdf(order: dict, client: dict) -> bytes:
    buf = io.BytesIO()
    W = A4[0] - 44*mm

    S_val  = _st("val1",  fontName=F_REG,  fontSize=9, textColor=C_DARK, leading=13)
    S_note = _st("note1", fontName=F_REG,  fontSize=8, textColor=C_GREY, leading=12)

    story = []
    now = datetime.now()
    validity = now + timedelta(days=30)
    order_num = order.get("order_num", "AW-000001")

    _kp_header(story, order_num, "Profesionální mytí fasád a oken drony", now, validity)
    _kp_parties(story, W, client, S_note)
    _kp_location(story, W, order.get("location", ""), S_val)

    # ─── Items table ──────────────────────────────────────────────────────────
    facade  = float(order.get("facade_area", 0))
    windows = float(order.get("window_area", 0))
    total   = (facade + windows) * PRICE_PER_M2

    col_w = [W - 85*mm, 28*mm, 25*mm, 30*mm]
    rows = [["Popis služby", "Plocha (m²)", "Cena / m² (bez DPH)", "Celkem"]]

    if facade > 0:
        rows.append(["Mytí fasády dronem", f"{facade:,.1f}",
                     f"{PRICE_PER_M2} Kč", f"{facade*PRICE_PER_M2:,.0f} Kč"])
    if windows > 0:
        rows.append(["Mytí oken dronem", f"{windows:,.1f}",
                     f"{PRICE_PER_M2} Kč", f"{windows*PRICE_PER_M2:,.0f} Kč"])
    rows.append(["", f"{facade+windows:,.1f} m²", "", f"{total:,.0f} Kč"])

    items_t = Table(rows, colWidths=col_w, repeatRows=1)
    items_t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0),   C_DARK),
        ("TEXTCOLOR",      (0,0), (-1,0),   C_WHITE),
        ("FONTNAME",       (0,0), (-1,0),   F_BOLD),
        ("FONTSIZE",       (0,0), (-1,0),   8),
        ("TOPPADDING",     (0,0), (-1,0),   8),
        ("BOTTOMPADDING",  (0,0), (-1,0),   8),
        ("FONTNAME",       (0,1), (-1,-2),  F_REG),
        ("FONTSIZE",       (0,1), (-1,-2),  9),
        ("TOPPADDING",     (0,1), (-1,-2),  7),
        ("BOTTOMPADDING",  (0,1), (-1,-2),  7),
        ("ROWBACKGROUNDS", (0,1), (-1,-2),  [C_WHITE, C_LGREY]),
        ("BACKGROUND",     (0,-1),(-1,-1),  C_BLUE_LT),
        ("FONTNAME",       (0,-1),(-1,-1),  F_BOLD),
        ("FONTSIZE",       (0,-1),(-1,-1),  10),
        ("TOPPADDING",     (0,-1),(-1,-1),  8),
        ("BOTTOMPADDING",  (0,-1),(-1,-1),  8),
        ("TEXTCOLOR",      (3,-1),(3,-1),   C_BLUE),
        ("ALIGN",          (1,0), (-1,-1),  "CENTER"),
        ("ALIGN",          (3,0), (3,-1),   "RIGHT"),
        ("VALIGN",         (0,0), (-1,-1),  "MIDDLE"),
        ("LEFTPADDING",    (0,0), (-1,-1),  8),
        ("RIGHTPADDING",   (0,0), (-1,-1),  8),
        ("LINEBELOW",      (0,-1),(-1,-1),  0, C_WHITE),
        ("BOX",            (0,0), (-1,-1),  0.5, colors.HexColor("#e0e0e0")),
    ]))
    story.append(items_t)
    story.append(Spacer(1, 8*mm))

    _kp_total_box(story, W, total)
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        "Ceny jsou uvedeny bez DPH. DPH bude účtováno dle platných předpisů.", S_note
    ))
    story.append(Spacer(1, 8*mm))

    _kp_conditions(story, W, order, validity, S_note)

    if order.get("notes"):
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph(f"<b>Poznámky:</b> {order['notes']}", S_note))

    _kp_footer(story, now)

    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=22*mm, rightMargin=22*mm,
                             topMargin=18*mm, bottomMargin=18*mm)
    doc.build(story)
    return buf.getvalue()


# ─── KP2: Horolezec + výměna mřížek ──────────────────────────────────────────

def generate_kp2_pdf(order: dict, client: dict,
                     climber_days: int = 3,
                     climber_total: float = 48000,
                     buildings: int = 4,
                     mrizky_per_building: int = 132,
                     mrizky_price_with_vat: float = 139,
                     consumables_per_building: float = 500) -> bytes:
    buf = io.BytesIO()
    W = A4[0] - 44*mm

    S_val    = _st("val2",   fontName=F_REG,  fontSize=9,   textColor=C_DARK, leading=13)
    S_note   = _st("note2",  fontName=F_REG,  fontSize=8,   textColor=C_GREY, leading=12)
    S_note_i = _st("notei2", fontName=F_ITAL, fontSize=7.5, textColor=C_GREY, leading=11)

    story = []
    now = datetime.now()
    validity = now + timedelta(days=30)
    order_num = order.get("order_num", "AW-000001")

    _kp_header(story, order_num, "Výškové práce a výměna mřížek", now, validity)
    _kp_parties(story, W, client, S_note)
    _kp_location(story, W, order.get("location", ""), S_val)

    # ─── Calculate prices ─────────────────────────────────────────────────────
    mrizky_total_ks   = buildings * mrizky_per_building
    mrizky_bez_dph    = round(mrizky_price_with_vat / VAT_RATE, 2)
    mrizky_celkem     = round(mrizky_total_ks * mrizky_bez_dph)
    consumables_total = buildings * consumables_per_building
    grand_total       = climber_total + mrizky_celkem + consumables_total

    # ─── Items table ──────────────────────────────────────────────────────────
    col_w = [W - 82*mm, 35*mm, 23*mm, 24*mm]
    rows = [["Popis prací", "Množství / Rozsah", "Cena / j. (bez DPH)", "Celkem"]]

    rows.append([
        "Práce horolezce",
        f"{climber_days} dny",
        "—",
        f"{climber_total:,.0f} Kč",
    ])
    rows.append([
        "Výměna mřížek *",
        f"{mrizky_total_ks} ks  ({mrizky_per_building} ks/dům)",
        f"{mrizky_bez_dph:.2f} Kč/ks",
        f"{mrizky_celkem:,.0f} Kč",
    ])
    rows.append([
        "Spotřební materiál (lepidlo apod.)",
        f"{buildings} domy × {consumables_per_building:.0f} Kč",
        "—",
        f"{consumables_total:,.0f} Kč",
    ])
    rows.append(["", "", "", f"{grand_total:,.0f} Kč"])

    items_t = Table(rows, colWidths=col_w, repeatRows=1)
    items_t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0),   C_DARK),
        ("TEXTCOLOR",      (0,0), (-1,0),   C_WHITE),
        ("FONTNAME",       (0,0), (-1,0),   F_BOLD),
        ("FONTSIZE",       (0,0), (-1,0),   8),
        ("TOPPADDING",     (0,0), (-1,0),   8),
        ("BOTTOMPADDING",  (0,0), (-1,0),   8),
        ("FONTNAME",       (0,1), (-1,-2),  F_REG),
        ("FONTSIZE",       (0,1), (-1,-2),  9),
        ("TOPPADDING",     (0,1), (-1,-2),  7),
        ("BOTTOMPADDING",  (0,1), (-1,-2),  7),
        ("ROWBACKGROUNDS", (0,1), (-1,-2),  [C_WHITE, C_LGREY]),
        ("BACKGROUND",     (0,-1),(-1,-1),  C_BLUE_LT),
        ("FONTNAME",       (0,-1),(-1,-1),  F_BOLD),
        ("FONTSIZE",       (0,-1),(-1,-1),  10),
        ("TOPPADDING",     (0,-1),(-1,-1),  8),
        ("BOTTOMPADDING",  (0,-1),(-1,-1),  8),
        ("TEXTCOLOR",      (3,-1),(3,-1),   C_BLUE),
        ("ALIGN",          (1,0), (-1,-1),  "CENTER"),
        ("ALIGN",          (3,0), (3,-1),   "RIGHT"),
        ("VALIGN",         (0,0), (-1,-1),  "MIDDLE"),
        ("LEFTPADDING",    (0,0), (-1,-1),  8),
        ("RIGHTPADDING",   (0,0), (-1,-1),  8),
        ("LINEBELOW",      (0,-1),(-1,-1),  0, C_WHITE),
        ("BOX",            (0,0), (-1,-1),  0.5, colors.HexColor("#e0e0e0")),
    ]))
    story.append(items_t)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "* <i>Mřížky lze dodat v barvě fasády. Jsme schopni nabídnout i více kusů, "
        "než je minimální požadavek.</i>",
        S_note_i
    ))
    story.append(Spacer(1, 6*mm))

    _kp_total_box(story, W, grand_total)
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        "Ceny jsou uvedeny bez DPH. DPH bude účtováno dle platných předpisů.", S_note
    ))
    story.append(Spacer(1, 8*mm))

    _kp_conditions(story, W, order, validity, S_note)

    if order.get("notes"):
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph(f"<b>Poznámky:</b> {order['notes']}", S_note))

    _kp_footer(story, now)

    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=22*mm, rightMargin=22*mm,
                             topMargin=18*mm, bottomMargin=18*mm)
    doc.build(story)
    return buf.getvalue()
