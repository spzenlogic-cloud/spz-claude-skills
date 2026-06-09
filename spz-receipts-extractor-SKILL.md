---
name: spz-receipts-extractor
description: >
  Extracts receipts from a PDF or image folder using AI vision. Renames each
  file to YYYYMMdd_VENDOR_CATEGORY_$X.XX.png (or _RET_ for refunds), writes
  receipts.csv (date, vendor, category, amount, items, refund, payment_method),
  and a processing_log.txt with OK/WARN/ERROR per file. Accepts PDF and images
  (PNG, JPG, JPEG, TIFF, WEBP). Non-receipt images are skipped and logged.
  Trigger when the user mentions receipts, expense images, scanning or organizing
  receipts, or asks to process a PDF or folder of receipt images.
---

# Receipt Processor Skill

## What this skill does

1. Finds a PDF or image file(s) in the user's folder
2. For PDFs: extracts each page as an individual PNG into an `input/` subfolder. For images: uses them directly.
3. Validates each image — if it does not look like a receipt, logs an error and skips it (no rename, no CSV row)
4. Reads valid receipts with AI vision to extract: date, vendor, category, amount, items, payment method, sale vs. refund
5. Renames each valid receipt file to the structured format above
6. Writes `receipts.csv` with one row per successfully processed receipt
7. Writes `processing_log.txt` recording every file, its renamed filename, status (OK / WARN / ERROR), and details
8. Unknown or unreadable fields become `UNKNOWN` as a placeholder

## CSV columns

| Column | Description |
|--------|-------------|
| `date` | Transaction date as MM/DD/YYYY |
| `filename` | The renamed PNG filename |
| `vendor` | Store name (e.g. HOMEDEPOT, WALMART) |
| `category` | Inferred category (HARDWARE, GROCERIES, etc.) |
| `amount` | Total charged as $X.XX |
| `items` | Human-readable description of purchased items |
| `refund` | `REFUND` if this is a return; empty for sales |
| `payment_method` | e.g. `CHASE VISA x0873`, `Store Credit x9267` |

---

## Step-by-step instructions

### Step 1 — Locate input files

The input can be either:
- **A PDF file** — each page is treated as one receipt (go to Step 2)
- **Image files** (PNG, JPG, JPEG, TIFF, WEBP) — every supported image file found in the folder is processed as a batch (skip Step 2)

**Scanning rules:**
- If the folder contains a PDF → use the PDF
- If the folder contains image files (no PDF) → collect ALL image files (PNG, JPG, JPEG, TIFF, WEBP) in the folder and process each one
- If both a PDF and image files exist → ask the user which to process
- If a specific file is mentioned by the user → use only that file
- If nothing is found → ask the user to point you to the file

Sort image files alphabetically before processing so the order is consistent and predictable.

### Step 2 — Extract PDF pages as PNGs (PDF only — skip for images)

Run the bundled extraction script (see `scripts/extract_pages.py`) to convert each PDF page into a PNG saved in `<pdf_folder>/input/`.

The skill directory path is available in your context as the location where this SKILL.md was loaded from. Use that path to locate the script.

```bash
python3 "<skill_dir>/scripts/extract_pages.py" \
  --pdf "<path_to_pdf>" \
  --output-dir "<pdf_folder>/input/" \
  --dpi 150
```

The script handles:
- One PNG per page, named `receipt_01.png`, `receipt_02.png`, etc.
- Automatic downscaling of very tall images (>1800px) to stay within the vision model's 2000×2000px limit

If the script fails, fall back to `pdf2image` inline, one page at a time:
```python
from pdf2image import convert_from_path
pages = convert_from_path(pdf, dpi=150, first_page=N, last_page=N)
pages[0].save(out_path, "PNG")
```

### Step 3 — Validate and read each image with vision

For each image file, use the Read tool to view it. **First, decide if it is a receipt.** An image qualifies as a receipt if it shows at least two of: a vendor/store name, a transaction date, a total or subtotal amount, line items with prices. If it fails this check, mark it as `ERROR` in the log, skip it entirely (no rename, no CSV row), and move on.

For images that pass validation, extract:

| Field | Notes |
|-------|-------|
| `date` | Transaction date on receipt → convert to `YYYYMMDD` for filename, `MM/DD/YYYY` for CSV. Use `UNKNOWN` if not visible. |
| `vendor` | Store name, UPPERCASE, no spaces. e.g. `HOMEDEPOT`, `WALMART`, `DOLLARTREE` |
| `category` | Infer from items: `GROCERIES`, `HARDWARE`, `RESTAURANT`, `FUEL`, `OFFICE`, `CLOTHING`, `PHARMACY`, `OTHER`, or `UNKNOWN` |
| `amount` | Final amount charged (after credits/discounts). Use the Visa/card charge if visible, otherwise the TOTAL line. |
| `is_refund` | `True` if the receipt says REFUND, RETURN, or shows a negative total |
| `items` | Short human-readable description of what was purchased. e.g. "Outlet, Tamper AFCI, Switch". Separate multiple items with commas.