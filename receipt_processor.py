"""
receipt_processor.py

Extracts receipt images from a multi-page PDF and renames them using
AI vision to read date, vendor, category, amount, and sale/refund type.

Naming format:
  Sale:   YYYYMMdd_VENDOR_CATEGORY_$X.XX.png
  Refund: YYYYMMdd_VENDOR_CATEGORY_RET_$X.XX.png

Unknown fields fall back to UNKNOWN.

Usage:
  python receipt_processor.py <input_pdf> [--output-dir <dir>] [--dpi <dpi>]

Requirements:
  pip install pdf2image pillow anthropic
  apt-get install poppler-utils  (for pdf2image)
"""

import os
import sys
import argparse
import base64
import json
import re
from pathlib import Path

try:
    from pdf2image import convert_from_path
except ImportError:
    sys.exit("Missing pdf2image. Run: pip install pdf2image")

try:
    from PIL import Image
except ImportError:
    sys.exit("Missing Pillow. Run: pip install pillow")

try:
    import anthropic
except ImportError:
    sys.exit("Missing anthropic SDK. Run: pip install anthropic")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MAX_IMAGE_HEIGHT = 1800   # px — keeps images under Claude's 2000x2000 limit
DEFAULT_DPI      = 150


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pdf_to_images(pdf_path: str, output_dir: str, dpi: int) -> list[str]:
    """Convert each PDF page to a PNG saved in output_dir. Returns file paths."""
    os.makedirs(output_dir, exist_ok=True)
    saved = []
    total_pages = None

    # Get page count first
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

    print(f"PDF has {total_pages} page(s). Extracting...")

    for i in range(1, total_pages + 1):
        pages = convert_from_path(pdf_path, dpi=dpi, first_page=i, last_page=i)
        img = pages[0]

        # Resize if too tall
        w, h = img.size
        if h > MAX_IMAGE_HEIGHT:
            ratio = MAX_IMAGE_HEIGHT / h
            img = img.resize((int(w * ratio), MAX_IMAGE_HEIGHT), Image.LANCZOS)

        out_path = os.path.join(output_dir, f"receipt_{i:02d}.png")
        img.save(out_path, "PNG")
        print(f"  Saved: receipt_{i:02d}.png  ({img.size[0]}x{img.size[1]})")
        saved.append(out_path)

    return saved


def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def read_receipt_with_ai(client: anthropic.Anthropic, image_path: str) -> dict:
    """
    Ask Claude to extract receipt fields. Returns a dict:
      { date, vendor, category, amount, is_refund }
    Falls back to UNKNOWN for unreadable fields.
    """
    b64 = image_to_base64(image_path)

    prompt = """You are reading a receipt image. Extract exactly these fields and return ONLY valid JSON — no markdown, no explanation.

{
  "date":      "YYYYMMDD or UNKNOWN",
  "vendor":    "store name in UPPERCASE, no spaces (e.g. HOMEDEPOT, WALMART, DOLLARTREE) or UNKNOWN",
  "category":  "one of: GROCERIES, HARDWARE, RESTAURANT, FUEL, OFFICE, CLOTHING, PHARMACY, OTHER, or UNKNOWN",
  "amount":    "total charged as a decimal number string, e.g. 21.60 — use the final amount paid (after credits/discounts), or UNKNOWN",
  "is_refund": true or false
}

Rules:
- date: use the transaction date on the receipt (MM/DD/YY or MM/DD/YYYY → convert to YYYYMMDD)
- vendor: strip spaces and punctuation, uppercase only
- category: infer from the items purchased
- amount: the bottom-line total charged (after any store credits applied)
- is_refund: true if the receipt says REFUND, RETURN, or shows negative totals"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text",  "text": prompt}
            ]
        }]
    )

    raw = response.content[0].text.strip()
    # Strip accidental markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$",       "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  WARNING: Could not parse AI response for {image_path}: {raw}")
        data = {}

    return {
        "date":      data.get("date",      "UNKNOWN"),
        "vendor":    data.get("vendor",    "UNKNOWN"),
        "category":  data.get("category",  "UNKNOWN"),
        "amount":    data.get("amount",    "UNKNOWN"),
        "is_refund": bool(data.get("is_refund", False)),
    }


def build_filename(meta: dict) -> str:
    """Build the final filename from extracted metadata."""
    date     = meta["date"]
    vendor   = meta["vendor"]
    category = meta["category"]
    amount   = meta["amount"]

    # Format amount
    if amount == "UNKNOWN":
        amt_str = "UNKNOWN"
    else:
        try:
            amt_str = f"${float(amount):.2f}"
        except ValueError:
            amt_str = f"${amount}"

    if meta["is_refund"]:
        return f"{date}_{vendor}_{category}_RET_{amt_str}.png"
    else:
        return f"{date}_{vendor}_{category}_{amt_str}.png"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract & rename receipts from a PDF.")
    parser.add_argument("pdf",        help="Path to the input PDF")
    parser.add_argument("--output-dir", default=None,       help="Where to save PNGs (default: <pdf_dir>/input/)")
    parser.add_argument("--dpi",        default=DEFAULT_DPI, type=int, help=f"Extraction DPI (default {DEFAULT_DPI})")
    args = parser.parse_args()

    pdf_path   = os.path.abspath(args.pdf)
    output_dir = args.output_dir or os.path.join(os.path.dirname(pdf_path), "input")

    if not os.path.exists(pdf_path):
        sys.exit(f"PDF not found: {pdf_path}")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY environment variable before running.")

    client = anthropic.Anthropic(api_key=api_key)

    # Step 1 — extract images
    image_paths = pdf_to_images(pdf_path, output_dir, args.dpi)

    # Step 2 & 3 — read each receipt and rename
    print(f"\nReading {len(image_paths)} receipt(s) with AI vision...")
    for img_path in image_paths:
        print(f"\n  {os.path.basename(img_path)}")
        meta     = read_receipt_with_ai(client, img_path)
        new_name = build_filename(meta)
        new_path = os.path.join(output_dir, new_name)

        os.rename(img_path, new_path)
        tag = "REFUND" if meta["is_refund"] else "SALE  "
        print(f"  [{tag}] → {new_name}")

    print(f"\nDone. {len(image_paths)} file(s) saved to: {output_dir}")


if __name__ == "__main__":
    main()
