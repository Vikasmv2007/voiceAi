"""GST maths in one place. Menu prices are BEFORE GST; GST is added on top.
With GST_RATE=5 the bill shows CGST 2.5% + SGST 2.5% (the usual split for a restaurant
inside one state). GST_RATE=0 (default) means no tax lines at all."""
from app import config


def tax_for(subtotal):
    rate = config.GST_RATE
    return int(round(subtotal * rate / 100)) if rate > 0 else 0


def split(tax):
    """(CGST, SGST) amounts in rupees; they always add up to the tax."""
    cgst = int(round(tax / 2))
    return cgst, tax - cgst


def breakdown(subtotal):
    tax = tax_for(subtotal)
    cgst, sgst = split(tax)
    return {"subtotal": subtotal, "tax": tax, "cgst": cgst, "sgst": sgst,
            "gst_rate": config.GST_RATE, "half_rate": config.GST_RATE / 2, "total": subtotal + tax}


def invoice_number(order_id, created_at):
    """INV-2026-000012 style number (year from the order's date)."""
    year = (created_at or "")[:4] or "0000"
    return f"INV-{year}-{order_id:06d}"
