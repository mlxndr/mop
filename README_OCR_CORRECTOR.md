# Parliamentary OCR Corrector

Automated OCR error detection and correction for 1834 British Parliamentary texts using 6 computational methods.

## Quick Start

```bash
# Install optional dependencies (recommended but not required)
pip install pyenchant python-Levenshtein

# Run with defaults
python parliamentary_ocr_corrector.py

# Or with custom options
python parliamentary_ocr_corrector.py \
  --input mirror-ocr-11-2-ALL-pages-parsed.json \
  --output-corrected mirror-ocr-11-2-ALL-pages-corrected.json \
  --threshold 0.90
```

## What It Does

The script implements 6 computational methods to detect and fix OCR errors:

1. **Dictionary-Based Spell Checking** - Validates words against modern English, historical (1828) dictionaries, and parliamentary terminology
2. **Character Confusion Detection** - Identifies common OCR errors (e.g., "X"→"K" in "DUEX"→"DUKE")
3. **Named Entity Consistency** - Ensures speakers, titles, and locations are spelled consistently
4. **N-gram Language Modeling** - Scores word sequences to find improbable combinations
5. **Edit Distance Correction** - Generates corrections using Levenshtein distance with context awareness
6. **Structural Pattern Validation** - Validates parliamentary formatting (speaker attributions, headers)

## Outputs

### 1. Corrected JSON File
`mirror-ocr-11-2-ALL-pages-corrected.json`
- Auto-applies corrections with confidence ≥ 0.90 (configurable)
- Same structure as input file

### 2. Corrections Report
`ocr-corrections-report.jsonl` (JSON Lines format)
```json
{
  "page_index": 6,
  "original_word": "DUEX",
  "position": 1247,
  "error_types": ["unknown_word", "confusion_pattern"],
  "context": "...Noble Lord opposite; but the DUEX of Wellington...",
  "suggested_corrections": [
    {"word": "DUKE", "confidence": 0.95}
  ]
}
```

### 3. Statistics Summary
`ocr-statistics.json`
```json
{
  "total_errors_found": 18472,
  "errors_by_type": {
    "unknown_word": 12384,
    "confusion_pattern": 3821
  },
  "top_errors": [
    {"original": "DUEX", "suggested": "DUKE", "count": 23}
  ]
}
```

## Bootstrap Data

On first run, the script automatically:

1. **Builds Parliamentary Lexicon** from `11-2-speeches.jsonl`
   - Extracts speaker names, debate titles, and parliamentary terms
   - Saves to `data/parliamentary_lexicon.txt`

2. **Downloads Webster's 1828 Dictionary** (or creates fallback)
   - Attempts download from GitHub
   - Falls back to basic historical spellings if download fails
   - Saves to `data/websters_1828.txt`

All bootstrap data is saved to `data/` directory for reuse.

## Command-Line Options

```
--input PATH              Input JSON file (default: mirror-ocr-11-2-ALL-pages-parsed.json)
--output-corrected PATH   Output corrected JSON (default: mirror-ocr-11-2-ALL-pages-corrected.json)
--output-report PATH      Output report JSONL (default: ocr-corrections-report.jsonl)
--threshold FLOAT         Auto-correction confidence threshold (default: 0.90)
--data-dir PATH           Data directory for dictionaries (default: data/)
```

## Dependencies

### Optional (but recommended)
```bash
pip install pyenchant python-Levenshtein
```

- **pyenchant**: Modern English dictionary checking (faster, more accurate)
- **python-Levenshtein**: Fast edit distance calculations (10x faster than pure Python)

The script includes fallback implementations if these aren't installed, but performance will be slower.

## Configuration

Character confusion patterns, historical spellings, and other settings are configured in the `CONFIG` dictionary at the top of `parliamentary_ocr_corrector.py`.

To preserve additional historical spellings, add them to:
```python
"preserve_historical_spellings": [
    "connexion", "shew", "shewn", ...
]
```

## Performance

- **~3,400 pages**: Approximately 5-15 minutes depending on system and dependencies
- **Bootstrap**: One-time setup (~30 seconds)
- **Memory**: ~500MB for full dataset

## Example Corrections

- `DUEX of WELLINGTON` → `DUKE of WELLINGTON`
- `calamour and coolness` → `calmness and coolness`
- `intolerance` → `indulgence` (context-dependent)
- `forlief Don Carlos` → `forbid Don Carlos`

## Troubleshooting

**"No module named 'enchant'"**
- Install: `pip install pyenchant`
- Or: Continue without (uses basic dictionary only)

**"Could not download Webster's 1828"**
- Normal if offline
- Script creates fallback wordlist automatically

**Low correction rate**
- Adjust `--threshold` lower (e.g., 0.80) to apply more corrections
- Review `ocr-corrections-report.jsonl` for manual verification

## Files Created

```
data/
├── parliamentary_lexicon.txt      # Auto-built from speeches
└── websters_1828.txt              # Auto-downloaded or fallback

ocr-corrections-report.jsonl       # Detailed error report
ocr-statistics.json                # Summary statistics
mirror-ocr-11-2-ALL-pages-corrected.json  # Corrected output
```
