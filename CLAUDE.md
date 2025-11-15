# CLAUDE.md

## Project Overview

This repository contains digitized British Parliamentary debate records from 1834, specifically volume "11-2" of what appears to be Hansard or similar parliamentary proceedings. The project stores both raw OCR-converted text and structured speech data extracted from historical parliamentary documents.

### Repository Purpose

- **Domain**: Historical parliamentary records / Natural Language Processing dataset
- **Time Period**: February 4, 1834 to October 23, 1834 (approximately 9 months)
- **Content**: Debates from both the House of Lords and House of Commons
- **Use Cases**: Text analysis, historical research, NLP training data, OCR quality verification

## Repository Structure

```
/home/user/mop/
├── .git/                                    # Git repository data
├── 11-2-speeches.jsonl                      # Structured speech records (33MB, ~20,897 speeches)
├── mirror-ocr-11-2-ALL-pages.json          # Raw OCR page data (31MB, 3,410 pages)
└── CLAUDE.md                                # This file
```

## Data Files

### 1. `11-2-speeches.jsonl` (Structured Speeches)

**Format**: JSON Lines (one JSON object per line)
**Size**: 33MB
**Records**: ~20,897 individual speeches/parliamentary contributions

**Schema**:
```json
{
  "id": "11-2_speech_000001",              // Unique identifier
  "house": "HOUSE OF LORDS",               // Either "HOUSE OF LORDS" or "HOUSE OF COMMONS"
  "date_iso": "1834-02-04",               // ISO 8601 date format
  "debate_title": "ADDRESS TO HIS MAJESTY.", // Topic of debate
  "speaker": "The DUKE of SUTHERLAND.",    // Speaker name and title
  "pages": [5],                            // Page number(s) in original document
  "text": "Full text of the speech..."     // Complete speech text
}
```

**Key Characteristics**:
- Line-delimited for efficient processing of large datasets
- Each line is a valid JSON object
- Cross-references pages in the OCR file via the `pages` field
- Chronologically ordered by date
- Spans both legislative chambers

### 2. `mirror-ocr-11-2-ALL-pages.json` (Raw OCR Pages)

**Format**: Single JSON object
**Size**: 31MB
**Pages**: 3,410 pages (indices 4-3414)

**Schema**:
```json
{
  "project": "mirror-ocr-11-2",
  "pages": [
    {
      "index": 4,                           // Page number in original document
      "markdown": "Full OCR text...",       // Complete page text in markdown format
      "global_index": 5                     // Global position reference
    }
  ]
}
```

**Key Characteristics**:
- Contains full document markdown
- Includes OCR artifacts and original formatting
- Page indices start at 4 (likely front matter excluded)
- Source material for the structured speeches file

## Working with the Data

### Reading JSONL Files

The speeches file uses JSON Lines format. Process line-by-line for memory efficiency:

**Python**:
```python
import json

with open('11-2-speeches.jsonl', 'r') as f:
    for line in f:
        speech = json.loads(line)
        # Process each speech
```

**Node.js**:
```javascript
const readline = require('readline');
const fs = require('fs');

const rl = readline.createInterface({
  input: fs.createReadStream('11-2-speeches.jsonl')
});

rl.on('line', (line) => {
  const speech = JSON.parse(line);
  // Process each speech
});
```

### Reading the OCR Pages File

The pages file is a single large JSON object:

**Python**:
```python
import json

with open('mirror-ocr-11-2-ALL-pages.json', 'r') as f:
    data = json.load(f)
    pages = data['pages']
    # Process pages
```

### Common Tasks

**Filter speeches by house**:
```python
lords_speeches = [json.loads(line) for line in open('11-2-speeches.jsonl')
                  if json.loads(line)['house'] == 'HOUSE OF LORDS']
```

**Filter by date range**:
```python
from datetime import datetime

target_date = datetime.fromisoformat('1834-02-04')
speeches = [json.loads(line) for line in open('11-2-speeches.jsonl')
            if datetime.fromisoformat(json.loads(line)['date_iso']) >= target_date]
```

**Cross-reference speech to OCR page**:
```python
import json

# Load OCR pages
with open('mirror-ocr-11-2-ALL-pages.json') as f:
    ocr_data = json.load(f)
    page_index = {p['index']: p for p in ocr_data['pages']}

# Load a speech and find its source pages
with open('11-2-speeches.jsonl') as f:
    speech = json.loads(f.readline())
    for page_num in speech['pages']:
        original_text = page_index.get(page_num, {}).get('markdown', 'Not found')
```

## Data Quality Notes

### OCR Artifacts

The original documents were OCR-scanned, so expect:
- Occasional typos (e.g., "DUEX" instead of "DUKE")
- Formatting inconsistencies
- Potential misrecognition of historical typefaces
- Period-specific spelling (e.g., "connexion" vs "connection")

### Historical Language

Parliamentary proceedings from 1834 use:
- Formal Victorian English
- Archaic titles and forms of address
- Historical place names and political references
- Long, complex sentence structures

## Development Workflow

### Git Workflow

**Current Branch**: `claude/claude-md-mi0mt02agdejgpdf-01PcvGebEepdRTNdcBUNByPw`

**Standard Workflow**:
1. Make changes to files
2. Stage changes: `git add <files>`
3. Commit with descriptive messages: `git commit -m "Description"`
4. Push to remote: `git push -u origin <branch-name>`

### Branch Naming Convention

- Feature branches: `claude/claude-md-<session-id>`
- Always push to the correct branch (starts with `claude/` and includes session ID)

### Commit Messages

Use clear, descriptive commit messages:
- "Add data processing script for speech analysis"
- "Fix date parsing in OCR extraction"
- "Update README with usage examples"

## AI Assistant Guidelines

### When Working with This Repository

1. **Understand the Data First**
   - This is a data repository, not a code repository
   - No build processes, tests, or compilation required
   - Focus on data analysis, extraction, and documentation

2. **File Operations**
   - **DO NOT** modify the original data files (`11-2-speeches.jsonl`, `mirror-ocr-11-2-ALL-pages.json`) unless explicitly requested
   - These are historical records and should be preserved as-is
   - Create new derived files for analysis results

3. **Common Requests**
   - Data analysis and statistics
   - Extracting specific speeches or debates
   - Cross-referencing between files
   - Creating derived datasets
   - Documentation and visualization

4. **Performance Considerations**
   - Files are large (64MB total)
   - Use streaming/line-by-line processing for JSONL files
   - Consider memory usage when loading full OCR pages file
   - Filter early in the pipeline to reduce data volume

5. **Historical Context**
   - This is 1834 British Parliament (reign of William IV)
   - Major topics include: slavery abolition, Irish affairs, European politics
   - Understand historical context when analyzing debates
   - Be aware of period-appropriate terminology

### Code Creation Guidelines

When creating analysis scripts:

1. **Always provide**:
   - Input validation
   - Error handling for malformed JSON
   - Progress indicators for long operations
   - Clear output formatting

2. **Prefer**:
   - Streaming processing over loading entire files
   - Standard library over external dependencies (when possible)
   - Command-line arguments for flexibility
   - JSON/CSV output for further processing

3. **Document**:
   - Purpose and usage of scripts
   - Required dependencies
   - Example commands
   - Expected output format

### Example Analysis Tasks

**Generate statistics**:
- Count speeches per house
- Speeches per speaker
- Debate topics distribution
- Date range coverage

**Text Analysis**:
- Word frequency analysis
- Named entity recognition
- Topic modeling
- Sentiment analysis (with historical context)

**Data Quality**:
- Identify OCR errors
- Check date continuity
- Validate cross-references
- Find incomplete records

**Visualization**:
- Timeline of debates
- Speaker participation
- Topic clustering
- Geographic/political affiliations

## Technical Specifications

### File Encodings
- **Encoding**: UTF-8
- **Line Endings**: Unix (LF)
- **JSON**: Standard JSON (RFC 8259)

### Data Validation

Expected invariants:
- All speech IDs follow pattern: `11-2_speech_NNNNNN`
- Dates are in ISO 8601 format: `YYYY-MM-DD`
- Date range: 1834-02-04 to 1834-10-23
- Houses: Only "HOUSE OF LORDS" or "HOUSE OF COMMONS"
- Page numbers are integers
- All page references should exist in OCR file

### Repository Metadata

- **Git Remote**: Local proxy at `127.0.0.1:17066/git/mlxndr/mop`
- **Repository Size**: ~64MB (excluding .git)
- **Initial Commit**: "Add existing 11-2 files"
- **File Count**: 2 primary data files

## Troubleshooting

### Common Issues

**Memory errors when loading OCR file**:
- Solution: Process pages incrementally or use streaming JSON parser

**JSON parsing errors**:
- Check for proper line separation in JSONL file
- Validate UTF-8 encoding
- Look for truncated lines

**Missing page references**:
- Note that OCR pages start at index 4, not 0
- Some speeches may span multiple pages
- Page numbers are from original document

## Additional Resources

### Related Projects

When working with this data, consider:
- **Historical Hansard Archives**: Official parliamentary records
- **NLP Libraries**: spaCy, NLTK for text processing
- **Historical Text Analysis**: Tools for period-appropriate language processing

### Useful Commands

```bash
# Count total speeches
wc -l 11-2-speeches.jsonl

# Extract all unique speakers
jq -r '.speaker' 11-2-speeches.jsonl | sort -u

# Filter House of Commons speeches
grep '"house": "HOUSE OF COMMONS"' 11-2-speeches.jsonl > commons.jsonl

# Get date range
jq -r '.date_iso' 11-2-speeches.jsonl | sort -u | head -1
jq -r '.date_iso' 11-2-speeches.jsonl | sort -u | tail -1

# Count pages
jq '.pages | length' mirror-ocr-11-2-ALL-pages.json
```

## Contact and Contribution

For questions, issues, or contributions:
1. Check existing git history for context
2. Maintain data integrity - do not modify source files
3. Document any derived data or analysis scripts
4. Use clear commit messages describing changes

---

**Last Updated**: 2025-11-15
**Document Version**: 1.0
