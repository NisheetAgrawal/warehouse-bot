from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime, timezone, timedelta
import io

BRAND_COLOR  = colors.HexColor("#1F4E79")
LIGHT_BLUE   = colors.HexColor("#EBF4FF")
ALT_ROW      = colors.HexColor("#F7FBFF")
RED_COLOR    = colors.HexColor("#CC0000")
GREEN_COLOR  = colors.HexColor("#1A7A1A")
ORANGE_COLOR = colors.HexColor("#C05000")
SECTION_COLORS = {
    "Solar Panel":  colors.HexColor("#FFF3CD"),
    "Inverter":     colors.HexColor("#D4EDDA"),
    "ACDB/DCDB":    colors.HexColor("#D1ECF1"),
    "Cable":        colors.HexColor("#E8D5F5"),
    "PVC Material": colors.HexColor("#FDEBD0"),
    "Structure":    colors.HexColor("#D6EAF8"),
    "General":      colors.HexColor("#F0F0F0"),
}
SECTION_ICONS = {
    "Solar Panel": "☀ Solar Panel", "Inverter": "⚡ Inverter",
    "ACDB/DCDB": "🔌 ACDB/DCDB", "Cable": "🔗 Cable",
    "PVC Material": "🧱 PVC Material", "Structure": "🏗 Structure", "General": "📦 General"
}

IST = timezone(timedelta(hours=5, minutes=30))


def generate_delivery_receipt(vehicle_no: str, operator: str, items: list, party: str = "") -> bytes:
    """
    items: list of dicts — brand, spec, type, quantity
    party: customer/receiver name (optional)
    Returns PDF bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    story = []
    now = datetime.now(IST)
    date_str = now.strftime("%d %b %Y")
    time_str = now.strftime("%I:%M %p") + " IST"

    # ── Header ──────────────────────────────────────────────────
    h_company = ParagraphStyle("hc", fontSize=18, textColor=BRAND_COLOR, fontName="Helvetica-Bold")
    h_sub     = ParagraphStyle("hs", fontSize=9,  textColor=colors.gray,  fontName="Helvetica")
    h_title   = ParagraphStyle("ht", fontSize=14, textColor=BRAND_COLOR,  fontName="Helvetica-Bold", alignment=TA_RIGHT)
    h_date    = ParagraphStyle("hd", fontSize=9,  textColor=colors.gray,  fontName="Helvetica", alignment=TA_RIGHT)

    header_data = [
        [Paragraph("GURUKRIPA ENTERPRISES", h_company),
         Paragraph("DELIVERY CHALLAN", h_title)],
        [Paragraph("Solar Equipment Supplier", h_sub),
         Paragraph(f"{date_str} &middot; {time_str}", h_date)]
    ]
    header_table = Table(header_data, colWidths=[100*mm, 81*mm])
    header_table.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("LINEBELOW",    (0,1), (-1,1),  1.5, BRAND_COLOR),
        ("BOTTOMPADDING",(0,1), (-1,1),  8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8*mm))

    # ── Meta box ─────────────────────────────────────────────────
    v_style = ParagraphStyle("vs", fontSize=16, textColor=RED_COLOR, fontName="Helvetica-Bold")
    lbl     = ParagraphStyle("lbl", fontSize=8, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_CENTER)
    val     = ParagraphStyle("val", fontSize=11, textColor=BRAND_COLOR, fontName="Helvetica-Bold", alignment=TA_CENTER)

    party_label = "PARTY / RECEIVER"
    meta_data = [
        [Paragraph("VEHICLE NUMBER", lbl), Paragraph("DATE & TIME", lbl),
         Paragraph("OPERATOR", lbl), Paragraph(party_label, lbl)],
        [Paragraph(vehicle_no, v_style),
         Paragraph(f"{date_str}<br/>{time_str}", val),
         Paragraph(operator, val),
         Paragraph(party or "—", val)]
    ]
    meta_table = Table(meta_data, colWidths=[46*mm, 46*mm, 46*mm, 43*mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), BRAND_COLOR),
        ("BACKGROUND",    (0,1), (-1,1), LIGHT_BLUE),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.white),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8*mm))

    # ── Items table (no rate/amount) ─────────────────────────────
    col_headers = ["#", "Brand", "Specification", "Quantity"]
    table_data  = [col_headers]

    total_qty = 0

    for i, item in enumerate(items):
        qty  = int(item.get("quantity", 0))
        unit = item.get("unit", "nos")
        total_qty += qty
        table_data.append([
            str(i + 1),
            item.get("brand", ""),
            f"{item.get('spec', '')} {item.get('type', '')}".strip(),
            f"{qty} {unit}",
        ])

    # Total row
    table_data.append(["", "", "TOTAL", str(total_qty)])

    col_widths  = [15*mm, 50*mm, 90*mm, 26*mm]
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    row_styles = [
        ("BACKGROUND",    (0,0),  (-1,0),  BRAND_COLOR),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),  (-1,0),  9),
        ("ALIGN",         (0,0),  (-1,-1), "CENTER"),
        ("ALIGN",         (1,1),  (2,-1),  "LEFT"),
        ("FONTSIZE",      (0,1),  (-1,-2), 9),
        ("GRID",          (0,0),  (-1,-1), 0.3, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",    (0,0),  (-1,-1), 6),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 6),
        ("BACKGROUND",    (0,-1), (-1,-1), BRAND_COLOR),
        ("TEXTCOLOR",     (0,-1), (-1,-1), colors.white),
        ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,-1), (-1,-1), 10),
    ]
    for i in range(1, len(table_data) - 1):
        bg = colors.white if i % 2 == 1 else ALT_ROW
        row_styles.append(("BACKGROUND", (0,i), (-1,i), bg))

    items_table.setStyle(TableStyle(row_styles))
    story.append(items_table)
    story.append(Spacer(1, 8*mm))

    # ── Disclaimer (Fix 5) ────────────────────────────────────────
    disclaimer_style = ParagraphStyle(
        "disclaimer",
        fontSize=8,
        textColor=colors.HexColor("#888888"),
        fontName="Helvetica-Oblique",
        alignment=TA_CENTER,
        leading=12,
    )
    story.append(Paragraph(
        "Agar is challan mein koi galti ho ya quantity mein koi issue ho toh "
        "delivery challan generation date se 2 din ke andar sampark karein.",
        disclaimer_style
    ))
    story.append(Spacer(1, 6*mm))

    # ── Signatures ───────────────────────────────────────────────
    sig_lbl = ParagraphStyle("sl", fontSize=9, textColor=colors.gray, fontName="Helvetica", alignment=TA_CENTER)
    sig_data = [
        [Paragraph("Driver / Receiver Signature", sig_lbl),
         Paragraph("Authorised by (Warehouse)", sig_lbl)],
        ["\n\n\n________________________",
         "\n\n\n________________________"]
    ]
    sig_table = Table(sig_data, colWidths=[90*mm, 91*mm])
    sig_table.setStyle(TableStyle([
        ("ALIGN",       (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",  (0,1), (-1,1), 4),
        ("FONTSIZE",    (0,1), (-1,1), 11),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph(
        f"Auto-generated by Warehouse Bot &middot; {date_str} {time_str}",
        ParagraphStyle("footer", fontSize=8, textColor=colors.gray,
                       alignment=TA_CENTER, fontName="Helvetica")
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def generate_stock_report_pdf(products: list) -> bytes:
    """
    products: list of dicts — section, brand, spec, type, quantity, unit
    Returns PDF bytes — full stock report grouped by section.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=12*mm, leftMargin=12*mm,
        topMargin=12*mm, bottomMargin=12*mm
    )
    story = []
    now = datetime.now(IST)
    date_str = now.strftime("%d %b %Y")
    time_str = now.strftime("%I:%M %p") + " IST"

    # ── Header ──────────────────────────────────────────────────
    h_company = ParagraphStyle("hc", fontSize=16, textColor=BRAND_COLOR, fontName="Helvetica-Bold")
    h_sub     = ParagraphStyle("hs", fontSize=8,  textColor=colors.gray,  fontName="Helvetica")
    h_title   = ParagraphStyle("ht", fontSize=13, textColor=BRAND_COLOR,  fontName="Helvetica-Bold", alignment=TA_RIGHT)
    h_date    = ParagraphStyle("hd", fontSize=8,  textColor=colors.gray,  fontName="Helvetica", alignment=TA_RIGHT)

    header_data = [
        [Paragraph("GURUKRIPA ENTERPRISES", h_company), Paragraph("STOCK REPORT", h_title)],
        [Paragraph("Solar Equipment Supplier", h_sub),  Paragraph(f"{date_str} &middot; {time_str}", h_date)]
    ]
    header_table = Table(header_data, colWidths=[100*mm, 81*mm])
    header_table.setStyle(TableStyle([
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
        ("LINEBELOW", (0,1), (-1,1), 1.5, BRAND_COLOR),
        ("BOTTOMPADDING", (0,1), (-1,1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5*mm))

    # ── Summary row ─────────────────────────────────────────────
    total   = len(products)
    in_stk  = sum(1 for p in products if p["quantity"] > 0)
    low_stk = sum(1 for p in products if 0 < p["quantity"] < 5)
    out_stk = total - in_stk

    lbl = ParagraphStyle("lbl2", fontSize=7, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_CENTER)
    val = ParagraphStyle("val2", fontSize=11, textColor=BRAND_COLOR, fontName="Helvetica-Bold", alignment=TA_CENTER)
    sum_data = [
        [Paragraph("TOTAL PRODUCTS", lbl), Paragraph("IN STOCK", lbl),
         Paragraph("LOW STOCK", lbl),      Paragraph("OUT OF STOCK", lbl)],
        [Paragraph(str(total), val),  Paragraph(str(in_stk), val),
         Paragraph(str(low_stk), val), Paragraph(str(out_stk), val)],
    ]
    sum_table = Table(sum_data, colWidths=[46*mm]*4)
    sum_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), BRAND_COLOR),
        ("BACKGROUND",    (0,1), (0,1), LIGHT_BLUE),
        ("BACKGROUND",    (1,1), (1,1), colors.HexColor("#D4EDDA")),
        ("BACKGROUND",    (2,1), (2,1), colors.HexColor("#FFF3CD")),
        ("BACKGROUND",    (3,1), (3,1), colors.HexColor("#FDDEDE")),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.white),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 5*mm))

    # ── Products grouped by section ──────────────────────────────
    sections = {}
    for p in products:
        sections.setdefault(p["section"], []).append(p)

    name_s  = ParagraphStyle("ns", fontSize=8, fontName="Helvetica")
    sec_s   = ParagraphStyle("ss", fontSize=9, fontName="Helvetica-Bold", textColor=BRAND_COLOR)
    qty_s   = ParagraphStyle("qs", fontSize=8, fontName="Helvetica-Bold", alignment=TA_CENTER)
    stat_ok = ParagraphStyle("sok", fontSize=7, fontName="Helvetica-Bold",
                              textColor=GREEN_COLOR, alignment=TA_CENTER)
    stat_lo = ParagraphStyle("slo", fontSize=7, fontName="Helvetica-Bold",
                              textColor=ORANGE_COLOR, alignment=TA_CENTER)
    stat_no = ParagraphStyle("sno", fontSize=7, fontName="Helvetica-Bold",
                              textColor=RED_COLOR, alignment=TA_CENTER)

    col_widths = [8*mm, 52*mm, 35*mm, 25*mm, 22*mm, 24*mm, 20*mm]
    col_header = ["#", "Brand / Product", "Specification", "Type / Details", "Qty", "Unit", "Status"]

    for section, items in sections.items():
        sec_bg = SECTION_COLORS.get(section, colors.HexColor("#F0F0F0"))
        sec_label = SECTION_ICONS.get(section, section)

        table_data = [[Paragraph(h, ParagraphStyle("ch", fontSize=8, fontName="Helvetica-Bold",
                        textColor=colors.white, alignment=TA_CENTER)) for h in col_header]]

        for i, p in enumerate(items):
            qty  = p["quantity"]
            unit = p["unit"]
            name = " ".join(filter(None, [p["brand"]]))
            spec = p.get("spec", "")
            typ  = p.get("type", "")
            if qty == 0:
                stat_p = Paragraph("OUT", stat_no)
                qty_p  = Paragraph("0", ParagraphStyle("qno", fontSize=8, fontName="Helvetica-Bold",
                                    textColor=RED_COLOR, alignment=TA_CENTER))
            elif qty < 5:
                stat_p = Paragraph("LOW", stat_lo)
                qty_p  = Paragraph(str(qty), ParagraphStyle("qlo", fontSize=8, fontName="Helvetica-Bold",
                                    textColor=ORANGE_COLOR, alignment=TA_CENTER))
            else:
                stat_p = Paragraph("✓ OK", stat_ok)
                qty_p  = Paragraph(str(qty), ParagraphStyle("qok", fontSize=8, fontName="Helvetica-Bold",
                                    textColor=GREEN_COLOR, alignment=TA_CENTER))

            table_data.append([
                Paragraph(str(i+1), ParagraphStyle("sr", fontSize=7, fontName="Helvetica",
                           textColor=colors.gray, alignment=TA_CENTER)),
                Paragraph(name, name_s),
                Paragraph(spec, name_s),
                Paragraph(typ, name_s),
                qty_p,
                Paragraph(unit, ParagraphStyle("us", fontSize=7, fontName="Helvetica",
                           textColor=colors.gray, alignment=TA_CENTER)),
                stat_p,
            ])

        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        row_styles = [
            ("BACKGROUND",    (0,0), (-1,0), BRAND_COLOR),
            ("GRID",          (0,0), (-1,-1), 0.3, colors.HexColor("#CCCCCC")),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]
        for r in range(1, len(table_data)):
            bg = colors.white if r % 2 == 1 else sec_bg
            row_styles.append(("BACKGROUND", (0,r), (-1,r), bg))
        tbl.setStyle(TableStyle(row_styles))

        story.append(Paragraph(sec_label, sec_s))
        story.append(Spacer(1, 1*mm))
        story.append(tbl)
        story.append(Spacer(1, 4*mm))

    # ── Footer ───────────────────────────────────────────────────
    story.append(Paragraph(
        f"Auto-generated by Warehouse Bot &middot; {date_str} {time_str}",
        ParagraphStyle("footer", fontSize=7, textColor=colors.gray,
                       alignment=TA_CENTER, fontName="Helvetica")
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
