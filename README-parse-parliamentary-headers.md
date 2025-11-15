# Parliamentary OCR Header Parser

This script processes OCR'd UK Parliamentary text from 1834, extracting page headers, removing footers, and joining hyphenated words across page boundaries.

## Purpose

The original OCR JSON contains parliamentary proceedings with:
- **Headers** at the beginning of pages (e.g., "HOUSE OF COMMONS", "HOUSE OF LORDS" with dates)
- **Footers** at the end of pages (e.g., "No. XL.—Sess. 1834.")
- **Hyphenated words** split across page boundaries

This script:
1. Extracts ONLY the `HOUSE OF LORDS`/`HOUSE OF COMMONS` headers (uses fuzzy matching for OCR errors)
2. Removes footers completely
3. Joins hyphenated words that span page boundaries (e.g., "some-" + "thing" → "something")
4. Keeps all debate content (section titles, speakers, text) in the `markdown` field

## Headers vs Content

**Headers extracted (removed from markdown):**

1. **HOUSE OF COMMONS/LORDS headers:**
   - `HOUSE OF COMMONS` or `HOUSE OF LORDS` (with optional dates)
   - Example: `HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834.`
   - Uses fuzzy matching to handle OCR errors

2. **Standalone date headers:**
   - Month name followed by numbers and punctuation
   - Example: `FEBRUARY 4`, `February 5, 18`, `MARCH 10, 1834.`
   - Allows numbers, punctuation, and I/i/l (for OCR errors and roman numerals)

**Requirements for extraction:**
- Must be followed by two line breaks (blank line after)
- Appears at the very start of a page

**These remain in markdown** (NOT extracted):
- Section titles like `PRIVATE BUSINESS`, `APPEALS`, `SELECT VESTRIES BILL`
- Speaker lines like `The EARL of ROSEBERY.—`
- Committee/topic names (e.g., `EDUCATION COMMITTEE.`)
- All debate text and proceedings

This is important because speeches can change multiple times within a single page, and section titles need to stay with their associated content.

## Footers

Footers matching these patterns are removed:
- `No. XL.—Sess. 1834.`
- `No. I.—Sept. 1834.`
- `No. XII.—Sezs. 1834.` (OCR variations)

## Hyphenated Word Joining

The script automatically joins hyphenated words split across page boundaries:

**Criteria for joining:**
- Previous page ends with `word-` (hyphen at end)
- Current page starts with lowercase word fragment (orphan)
- Orphan must be lowercase (not capitalized - indicates continuation)
- Orphan must be ≤15 characters
- Orphan cannot be a month name

**Example:**
```
Page 10: "...some incredible develop-"
Page 11: "ment in the proceedings..."
→
Page 10: "...some incredible development"
Page 11: "in the proceedings..."
```

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
  "header": "HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834.",
  "markdown": "SELECT VESTRIES BILL.\n\nOn the motion of EARL GREY..."
}
```

Note: `header` is now a single string (not an array), and section titles like "SELECT VESTRIES BILL" remain in the markdown.

## Statistics

From processing `mirror-ocr-11-2-ALL-pages.json`:
- **Total pages:** 3,410
- **Headers extracted:** 339 total
  - HOUSE OF COMMONS/LORDS: 320
  - Date headers: 19
- **Hyphenated words joined:** ~684 successful joins
- **Pages still ending with hyphens:** 48 (legitimate hyphens or edge cases)
- **Footers removed:** All instances

### Example Headers Extracted

**HOUSE headers:**
- `HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834.`
- `HOUSE OF COMMONS.`
- `HOUSE OF COMMONS, 110 181001` (OCR error, still matched)

**Date headers:**
- `FEBRUARY 4.1`
- `February 5, 18`
- `February 11.1`
- `FEBRUARY 10.`
