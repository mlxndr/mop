# Parliamentary OCR Header Parser

This script processes OCR'd UK Parliamentary text from 1834, extracting page headers into separate JSON fields and removing page footers.

## Purpose

The original OCR JSON contains parliamentary proceedings with:
- **Headers** at the beginning of pages (e.g., "HOUSE OF COMMONS", "HOUSE OF LORDS" with dates and section titles)
- **Footers** at the end of pages (e.g., "No. XL.—Sess. 1834.")

This script:
1. Extracts headers into a separate `header` field (as an array of strings)
2. Removes footers completely
3. Keeps the remaining content in the `markdown` field

## Headers vs Content

The script distinguishes between:

**Headers** (extracted):
- `HOUSE OF COMMONS` or `HOUSE OF LORDS` followed by dates
- Section titles like `PRIVATE BUSINESS`, `APPEALS`, `SELECT VESTRIES BILL`
- These appear at the start of pages

**Content** (remains in markdown):
- Speaker lines like `The EARL of ROSEBERY.—`
- Committee/topic names that appear within speeches (e.g., `EDUCATION COMMITTEE.`)
- All debate text and proceedings

## Footers

Footers matching these patterns are removed:
- `No. XL.—Sess. 1834.`
- `No. I.—Sept. 1834.`
- `No. XII.—Sezs. 1834.` (OCR variations)

## Usage

```bash
# Basic usage (creates *-parsed.json)
python3 parse_parliamentary_headers.py mirror-ocr-11-2-ALL-pages.json

# Specify output file
python3 parse_parliamentary_headers.py input.json output.json
```

## Output Format

Before:
```json
{
  "index": 4,
  "markdown": "HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834.\n\nSELECT VESTRIES BILL.\n\nOn the motion of EARL GREY..."
}
```

After:
```json
{
  "index": 4,
  "header": [
    "HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834.",
    "SELECT VESTRIES BILL."
  ],
  "markdown": "On the motion of EARL GREY..."
}
```

## Statistics

From processing `mirror-ocr-11-2-ALL-pages.json`:
- Total pages: 3,410
- Pages with headers: 320
- Pages with multi-line headers: 245
- Footers removed: All instances
