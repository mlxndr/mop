# Speaker ID Assignment Guide

## Overview

The `assign_speaker_ids.py` script creates unique identifiers for speakers in the 1834 Parliamentary corpus, handling name variations, titles, and fuzzy matching.

## The Challenge

Speaker names in historical parliamentary records are messy:

```
"The DUKE of SUTHERLAND."
"Duke of Sutherland"
"SUTHERLAND"
```

These should all map to the same person: **SPEAKER_001**

## Quick Start

```bash
python assign_speaker_ids.py
```

This creates:
1. `11-2-speeches-with-ids.jsonl` - Original speeches + `speaker_id` field
2. `speaker_registry.json` - Canonical speaker list with metadata
3. `speaker_stats.json` - Statistics per speaker
4. `ambiguous_speakers.json` - Cases needing manual review (if any)

## What It Does

### 1. Name Normalization

Converts raw names to canonical form:

| Raw Name | Normalized |
|----------|------------|
| "The DUKE of SUTHERLAND." | "Duke of Sutherland" |
| "Mr. ROBERT WALLACE" | "Robert Wallace" |
| "Sir Francis Freeling" | "Francis Freeling" |
| "THE LORD CHANCELLOR" | "Lord Chancellor" |

### 2. Fuzzy Matching

Uses similarity scoring to match variations:

```python
"Duke of Sutherland"  ↔  "Duke of Sunderland"   # 95% similar → same person
"Robert Wallace"      ↔  "Robert Wallase"       # 93% similar → same person
"Earl of Essex"       ↔  "Earl of Sussex"       # 85% similar → same person
```

**Threshold:** 85% similarity by default (configurable with `--threshold`)

### 3. Surname Extraction

Handles British nobility naming:

```python
"Duke of Sutherland" → surname: "Sutherland"
"Earl of Essex"      → surname: "Essex"
"Robert Wallace"     → surname: "Wallace"
```

### 4. Title Handling

**Keeps substantive titles:**
- Duke, Earl, Lord, Viscount, Baron (part of identity)

**Removes honorifics:**
- Mr., Mrs., Sir, Hon. (just courtesy)

### 5. Ambiguity Detection

Flags cases where multiple speakers might match:

```json
{
  "new_name": "Mr. Smith",
  "candidates": [
    {"speaker_id": "SPEAKER_042", "name": "John Smith", "similarity": 0.87},
    {"speaker_id": "SPEAKER_156", "name": "James Smith", "similarity": 0.86}
  ]
}
```

## Output Format

### 1. Speeches with IDs (JSONL)

Original speeches with `speaker_id` added:

```json
{
  "id": "11-2_speech_000001",
  "house": "HOUSE OF LORDS",
  "date_iso": "1834-02-04",
  "debate_title": "ADDRESS TO HIS MAJESTY.",
  "speaker": "The DUKE of SUTHERLAND.",
  "speaker_id": "SPEAKER_001",
  "pages": [5],
  "text": "Full speech text..."
}
```

### 2. Speaker Registry (JSON)

Canonical speaker information:

```json
{
  "SPEAKER_001": {
    "canonical_name": "Duke of Sutherland",
    "variations": [
      "The DUKE of SUTHERLAND.",
      "Duke of Sutherland",
      "SUTHERLAND"
    ],
    "type": "person",
    "houses": ["HOUSE OF LORDS"],
    "first_seen": "1834-02-04"
  },
  "SPEAKER_002": {
    "canonical_name": "Robert Wallace",
    "variations": [
      "Mr. ROBERT WALLACE",
      "Robert Wallace",
      "Mr. Wallace"
    ],
    "type": "person",
    "houses": ["HOUSE OF COMMONS"],
    "first_seen": "1834-02-04"
  }
}
```

### 3. Speaker Statistics (JSON)

Per-speaker analytics:

```json
{
  "SPEAKER_001": {
    "speech_count": 156,
    "total_words": 45623,
    "houses": ["HOUSE OF LORDS"],
    "debates": ["ADDRESS TO HIS MAJESTY.", "CHURCH REVENUES.", ...],
    "date_range": {
      "first": "1834-02-04",
      "last": "1834-10-23"
    }
  }
}
```

## Advanced Usage

### Custom Similarity Threshold

More strict matching (fewer variations grouped):

```bash
python assign_speaker_ids.py --threshold 0.90
```

More lenient matching (more variations grouped):

```bash
python assign_speaker_ids.py --threshold 0.80
```

### Custom Output Files

```bash
python assign_speaker_ids.py \
  --input my-speeches.jsonl \
  --output-speeches speeches-with-ids.jsonl \
  --output-registry my-speaker-registry.json \
  --output-stats my-speaker-stats.json
```

## Analyzing Results

### 1. Find Most Active Speakers

```python
import json

with open('speaker_stats.json') as f:
    stats = json.load(f)

# Sort by speech count
sorted_speakers = sorted(stats.items(), key=lambda x: x[1]['speech_count'], reverse=True)

print("Top 10 speakers:")
for i, (speaker_id, data) in enumerate(sorted_speakers[:10], 1):
    print(f"{i}. {speaker_id}: {data['speech_count']} speeches")
```

### 2. Get All Speeches by a Speaker

```python
import json

target_speaker = "SPEAKER_001"
speeches = []

with open('11-2-speeches-with-ids.jsonl') as f:
    for line in f:
        speech = json.loads(line)
        if speech['speaker_id'] == target_speaker:
            speeches.append(speech)

print(f"Found {len(speeches)} speeches by {target_speaker}")
```

### 3. Look Up Speaker Info

```python
import json

with open('speaker_registry.json') as f:
    registry = json.load(f)

speaker_id = "SPEAKER_001"
info = registry[speaker_id]

print(f"Canonical name: {info['canonical_name']}")
print(f"Name variations: {', '.join(info['variations'])}")
print(f"Houses: {', '.join(info['houses'])}")
print(f"First seen: {info['first_seen']}")
```

### 4. Cross-House Speakers

Find speakers who appeared in both houses:

```python
import json

with open('speaker_registry.json') as f:
    registry = json.load(f)

cross_house = []
for speaker_id, info in registry.items():
    if len(info['houses']) > 1:
        cross_house.append((speaker_id, info['canonical_name'], info['houses']))

print(f"Speakers appearing in multiple houses: {len(cross_house)}")
for speaker_id, name, houses in cross_house:
    print(f"  {speaker_id}: {name} → {houses}")
```

## Manual Review of Ambiguous Cases

If `ambiguous_speakers.json` is created, review it:

```json
[
  {
    "new_name": "Mr. Smith",
    "normalized": "Smith",
    "candidates": [
      {"speaker_id": "SPEAKER_042", "name": "John Smith", "similarity": 0.87},
      {"speaker_id": "SPEAKER_156", "name": "James Smith", "similarity": 0.86}
    ]
  }
]
```

**Resolution:**
1. Look at speeches by each candidate speaker
2. Check dates, debates, context
3. Manually merge IDs if they're the same person
4. Keep separate if they're different people

## Integration with Corpus Annotation

Use speaker IDs in the annotated corpus:

```bash
# 1. Assign speaker IDs
python assign_speaker_ids.py

# 2. Create annotated corpus with speaker IDs
python create_annotated_corpus.py --speeches 11-2-speeches-with-ids.jsonl
```

This preserves `speaker_id` in all corpus formats (CoNLL-U, TEI XML, etc.)

## Common Patterns Handled

### Nobility Titles

```
"The DUKE of SUTHERLAND"
"Duke of Sutherland"
"SUTHERLAND"
→ All map to: SPEAKER_001 (Duke of Sutherland)
```

### Name with/without Honorific

```
"Mr. Robert Wallace"
"Robert Wallace"
"Mr. Wallace"
→ All map to: SPEAKER_002 (Robert Wallace)
```

### Case Variations

```
"ROBERT WALLACE"
"Robert Wallace"
"Robert wallace"
→ All map to: SPEAKER_002 (Robert Wallace)
```

### OCR Errors (if within threshold)

```
"Robert Wallace"
"Robert Wallase"  (OCR error: c→s)
→ Map to: SPEAKER_002 (Robert Wallace)
```

### Functional Titles

These get separate IDs:

```
"The SPEAKER"        → FUNCTIONAL_0001
"The CHAIRMAN"       → FUNCTIONAL_0002
"The LORD CHANCELLOR" → FUNCTIONAL_0003
```

## Speaker ID Format

- **Person:** `SPEAKER_0001`, `SPEAKER_0002`, etc.
- **Functional:** `FUNCTIONAL_0001`, `FUNCTIONAL_0002`, etc.

IDs are assigned in order of first appearance.

## Validation

After running, validate results:

```python
import json

# Count speakers
with open('speaker_registry.json') as f:
    registry = json.load(f)
print(f"Total unique speakers: {len(registry)}")

# Check for duplicates
names = [info['canonical_name'] for info in registry.values()]
duplicates = [name for name in names if names.count(name) > 1]
if duplicates:
    print(f"⚠️  Duplicate canonical names: {set(duplicates)}")
else:
    print("✓ No duplicate canonical names")

# Verify all speeches have IDs
with open('11-2-speeches-with-ids.jsonl') as f:
    missing = 0
    for line in f:
        speech = json.loads(line)
        if 'speaker_id' not in speech:
            missing += 1

    if missing:
        print(f"⚠️  {missing} speeches missing speaker_id")
    else:
        print("✓ All speeches have speaker_id")
```

## Limitations & Caveats

### 1. Historical Accuracy

The script uses **fuzzy matching**, which may:
- ✓ Correctly group "Duke of Sutherland" variations
- ✗ Incorrectly merge two people with similar names

**Solution:** Check `ambiguous_speakers.json` and manually review

### 2. Title Changes

If someone was promoted during 1834:
- February: "Mr. John Smith"
- October: "Sir John Smith"

These will be grouped (same surname, high similarity), but you may want to verify.

### 3. Common Surnames

Multiple "Mr. Smith"s will be flagged as ambiguous. Manual review required.

### 4. Maiden Names

Women who changed names during this period won't be automatically linked.

## Best Practices

1. **Start with default threshold (0.85)**
2. **Review ambiguous cases** before using in research
3. **Cross-check with historical records** (Hansard, biographical dictionaries)
4. **Document any manual corrections** you make
5. **Version your speaker registry** if you make changes

## Research Applications

With speaker IDs, you can:

1. **Track individual speakers** over time
2. **Compare speaking patterns** between Lords/Commons
3. **Analyze vocabulary** by speaker
4. **Study debate participation** networks
5. **Examine political alignments** through co-occurrence
6. **Measure speech length** distribution per speaker
7. **Identify most influential** speakers by mention count

## Example: Create Speaker Timeline

```python
import json
from datetime import datetime
from collections import defaultdict

# Load speeches with IDs
speeches_by_speaker = defaultdict(list)

with open('11-2-speeches-with-ids.jsonl') as f:
    for line in f:
        speech = json.loads(line)
        speeches_by_speaker[speech['speaker_id']].append({
            'date': speech['date_iso'],
            'debate': speech['debate_title']
        })

# Create timeline for a speaker
target = "SPEAKER_001"
timeline = sorted(speeches_by_speaker[target], key=lambda x: x['date'])

print(f"Timeline for {target}:")
for entry in timeline[:10]:  # First 10
    print(f"  {entry['date']}: {entry['debate']}")
```

## Further Enhancement

To improve speaker identification:

1. **Add biographical data** (birth year, constituency, party)
2. **Use historical Hansard records** for validation
3. **Implement peer review** workflow for ambiguous cases
4. **Add constituency information** to help distinguish MPs
5. **Train ML model** on confirmed speaker pairs

---

**Questions or issues?** Check the ambiguous cases file and manually review uncertain matches.
