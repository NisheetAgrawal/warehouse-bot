from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from datetime import datetime, timezone, timedelta
import io

BRAND_COLOR = colors.HexColor("#1F4E79")
LIGHT_BLUE  = colors.HexColor("#EBF4FF")
ALT_ROW     = colors.HexColor("#F7FBFF")
RED_COLOR   = colors.HexColor("#CC0000")

IST = timezone(timedelta(hours=5, minutes=30))


def generate_delivery_receipt(vehicle_no: str, operator: str, items: list) -> bytes:
    """
    items: list of dicts — brand, spec, type, quantity
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
        [Paragraph("SOLAR WAREHOUSE", h_company),
         Paragraph("DELIVERY CHALLAN", h_title)],
        [Paragraph("Inventory Management System", h_sub),
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

    meta_data = [
        [Paragraph("VEHICLE NUMBER", lbl), Paragraph("DATE & TIME", lbl), Paragraph("OPERATOR", lbl)],
        [Paragraph(vehicle_no, v_style),
         Paragraph(f"{date_str}<br/>{time_str}", val),
         Paragraph(operator, val)]
    ]
    meta_table = Table(meta_data, colWidths=[61*mm, 60*mm, 60*mm])
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
        qty = int(item.get("quantity", 0))
        total_qty += qty
        table_data.append([
            str(i + 1),
            item.get("brand", ""),
            f"{item.get('spec', '')} {item.get('type', '')}".strip(),
            str(qty),
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
    story.append(Spacer(1, 12*mm))

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
