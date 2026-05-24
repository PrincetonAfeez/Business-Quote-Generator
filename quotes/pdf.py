from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe(text):
    return escape(str(text or ""))


def _safe_multiline(text):
    return _safe(text).replace("\n", "<br/>")


def render_quote_pdf(quote, profile=None):
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=48, leftMargin=48, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    story = []

    business_name = profile.business_name if profile else "Business Quote"
    address = _safe_multiline(profile.address if profile else "")
    tax_id = profile.tax_id if profile else ""
    logo = getattr(profile, "logo", None) if profile else None
    if logo and getattr(logo, "name", "") and getattr(logo, "path", None):
        try:
            story.append(Image(logo.path, width=1.5 * inch, height=1.5 * inch, kind="proportional"))
            story.append(Spacer(1, 0.1 * inch))
        except (OSError, ValueError):
            pass
    story.append(Paragraph(f"<b>{_safe(business_name)}</b>", styles["Title"]))
    if address:
        story.append(Paragraph(address, styles["Normal"]))
    if tax_id:
        story.append(Paragraph(f"Tax ID: {_safe(tax_id)}", styles["Normal"]))
    story.append(Paragraph(f"Status: <b>{_safe(quote.get_status_display())}</b>", styles["Normal"]))
    story.append(Spacer(1, 0.25 * inch))

    client_lines = [quote.client.name, quote.client.company, quote.client.email, quote.client.billing_address]
    client_block = "<br/>".join(_safe(line) for line in client_lines if line)
    meta = [
        ["Quote", quote.number],
        ["Issue date", quote.issue_date.strftime("%Y-%m-%d")],
        ["Expiry date", quote.expiry_date.strftime("%Y-%m-%d")],
        ["Client", Paragraph(client_block or "Client", styles["Normal"])],
    ]
    meta_table = Table(meta, colWidths=[1.3 * inch, 4.8 * inch])
    meta_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569"))]))
    story.append(meta_table)
    story.append(Spacer(1, 0.25 * inch))

    rows = [["Description", "Qty", "Unit", "Unit price", "Line total"]]
    for item in quote.line_items.order_by("position", "id"):
        unit_label = item.catalog_item.get_unit_display() if item.catalog_item else ""
        rows.append([
            Paragraph(_safe(item.description), styles["Normal"]),
            f"{item.quantity}",
            _safe(unit_label),
            f"${item.unit_price:,.2f}",
            f"${item.line_total:,.2f}",
        ])
    table = Table(rows, colWidths=[3.0 * inch, 0.6 * inch, 0.65 * inch, 1 * inch, 1 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.25 * inch))

    totals = [
        ["Subtotal", f"${quote.subtotal:,.2f}"],
        ["Discount", f"-${quote.discount_amount:,.2f}"],
        ["Tax", f"${quote.tax_amount:,.2f}"],
        ["Total", f"${quote.total:,.2f}"],
    ]
    totals_table = Table(totals, colWidths=[4.9 * inch, 1.2 * inch])
    totals_table.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    story.append(totals_table)
    story.append(Spacer(1, 0.25 * inch))

    if quote.terms:
        story.append(Paragraph("<b>Terms</b>", styles["Heading3"]))
        story.append(Paragraph(_safe_multiline(quote.terms), styles["Normal"]))
    if quote.notes:
        story.append(Paragraph("<b>Notes</b>", styles["Heading3"]))
        story.append(Paragraph(_safe_multiline(quote.notes), styles["Normal"]))
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("Signature: ________________________________", styles["Normal"]))

    document.build(story)
    buffer.seek(0)
    return buffer
