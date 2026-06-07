# spz-claude-skills

Claude Cowork skills created by SPZ — personal automation tools built with [Anthropic Claude](https://claude.ai).

---

## Skills

### 🧾 spz-receipts-extractor

Extracts receipt images from a multi-page PDF or a folder of images, reads each one with AI vision, renames the files to a structured format, and generates a CSV summary.

**Output file naming:**
```
Sale:   YYYYMMdd_VENDOR_CATEGORY_$X.XX.png
Refund: YYYYMMdd_VENDOR_CATEGORY_RET_$X.XX.png
```

**Also produces:**
- `receipts.csv` — one row per receipt with date, vendor, category, amount, items, refund flag, and payment method
- `processing_log.txt` — full log with OK / WARN / ERROR status per file

**Accepts:**
- Multi-page PDF (each page = one receipt)
- Individual image files: PNG, JPG, JPEG, TIFF, WEBP
- Mixed folders — non-receipt images are detected and logged as errors, not renamed

**Example output:**

| date | filename | vendor | category | amount | items | refund | payment_method |
|------|----------|--------|----------|--------|-------|--------|----------------|
| 05/22/2026 | 20260522_DOLLARTREE_HARDWARE_$3.25.png | DOLLARTREE | HARDWARE | $3.25 | Super Glue 2G 4PK, Masking Tape 4FT | | CHASE VISA x0873 |
| 05/28/2026 | 20260528_HOMEDEPOT_HARDWARE_RET_$39.04.png | HOMEDEPOT | HARDWARE | $39.04 | Lumber 2x6x8ft, Concrete Mix 60lb | REFUND | CHASE VISA x0873 |

---

## How to install a skill

1. Download the `.skill` file from this repo
2. Open **Claude Cowork** on your desktop
3. Click the card that appears in chat and hit **Save skill**
4. The skill is now installed — Claude will trigger it automatically when relevant

---

## How to use spz-receipts-extractor

1. Connect your folder in Claude Cowork
2. Drop your receipt PDF or image files into that folder
3. Say: **"process my receipts"** or **"extract receipts from my PDF"**
4. Claude runs the skill automatically — no further input needed
5. Check the folder for renamed files, `receipts.csv`, and `processing_log.txt`

---

## Requirements

The skill runs inside Claude Cowork's sandbox which has these pre-installed:
- `pdf2image`, `Pillow`, `pdfplumber`
- `poppler-utils`

No API key needed — Claude handles AI vision internally.

---

## Files in this repo

```
spz-receipts-extractor/
├── SKILL.md                  ← skill instructions (what Claude reads)
└── scripts/
    └── extract_pages.py      ← bundled PDF extraction script
receipt_processor.py          ← standalone Python script (requires ANTHROPIC_API_KEY)
spz-receipts-extractor.skill  ← installable skill file (zip)
```

---

## License

MIT — free to use, share, and modify with credit.
