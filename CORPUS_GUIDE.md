# Parliamentary Corpus Annotation Guide

## Overview

This guide explains how to convert your spell-checked 1834 UK Parliamentary texts into a fully annotated linguistic corpus using `create_annotated_corpus.py`.

## What Gets Annotated?

For each token (word) in the corpus, you'll get:

1. **Part-of-Speech (POS)** tags - noun, verb, adjective, etc.
2. **Lemmas** - base form (e.g., "running" → "run")
3. **Morphological features** - tense, number, case, etc.
4. **Dependency parsing** - grammatical relationships between words
5. **Named Entities** - people, places, organizations, dates
6. **Sentence boundaries** - automatic sentence segmentation

## Installation

### 1. Install spaCy

```bash
pip install spacy
```

### 2. Download a Language Model

Choose one based on your needs:

```bash
# Small model (fastest, 12MB) - good for testing
python -m spacy download en_core_web_sm

# Medium model (balanced, 40MB) - recommended
python -m spacy download en_core_web_md

# Large model (most accurate, 560MB) - best quality
python -m spacy download en_core_web_lg

# Transformer model (state-of-the-art, 438MB) - highest accuracy but slower
python -m spacy download en_core_web_trf
```

**Recommendation for 1834 Parliamentary texts:**
- Use `en_core_web_lg` for production (best balance of speed/accuracy)
- Use `en_core_web_sm` for quick testing

## Usage

### Quick Start (Test on 100 speeches)

```bash
python create_annotated_corpus.py --sample 100
```

This creates:
- `corpus_output/parliamentary-1834.conllu` (CoNLL-U format)
- `corpus_output/parliamentary-1834.vert` (Vertical format)
- `corpus_output/parliamentary-1834.xml` (TEI XML)
- `corpus_output/parliamentary-1834-annotated.jsonl` (JSON with annotations)

### Full Corpus (All ~21,000 speeches)

```bash
python create_annotated_corpus.py
```

**Estimated time:** 30-60 minutes for full corpus (depends on model size)

### Advanced Options

```bash
# Use different spaCy model
python create_annotated_corpus.py --spacy-model en_core_web_sm

# Output only specific format
python create_annotated_corpus.py --format conllu

# Custom output directory
python create_annotated_corpus.py --output-dir my_corpus

# Process first 500 speeches with small model
python create_annotated_corpus.py --sample 500 --spacy-model en_core_web_sm
```

## Output Formats Explained

### 1. CoNLL-U Format (.conllu)

**Best for:** Linguistic research, dependency parsing analysis

Standard format used by Universal Dependencies project. Each token on one line with tab-separated fields:

```
# sent_id = 11-2_speech_000001-1
# text = The DUKE of SUTHERLAND moved an Address to his Majesty.
# speaker = The DUKE of SUTHERLAND.
# house = HOUSE OF LORDS
# date = 1834-02-04
1	The	the	DET	DT	Definite=Def|PronType=Art	2	det	_	_
2	DUKE	duke	NOUN	NN	Number=Sing	6	nsubj	_	_
3	of	of	ADP	IN	_	4	case	_	_
4	SUTHERLAND	Sutherland	PROPN	NNP	Number=Sing	2	nmod	_	_
5	moved	move	VERB	VBD	Mood=Ind|Tense=Past|VerbForm=Fin	0	root	_	_
6	an	a	DET	DT	Definite=Ind|PronType=Art	7	det	_	_
7	Address	address	NOUN	NN	Number=Sing	5	obj	_	_
...
```

**Columns:**
1. ID - Token index in sentence
2. FORM - The word as it appears
3. LEMMA - Base form
4. UPOS - Universal POS tag
5. XPOS - Language-specific POS (Penn Treebank)
6. FEATS - Morphological features
7. HEAD - Head of dependency relation
8. DEPREL - Dependency relation type
9. DEPS - Enhanced dependencies (unused)
10. MISC - Miscellaneous (unused)

**Use with:**
- [UD Tools](https://universaldependencies.org/tools.html)
- Python: `conllu` library
- R: `udpipe` package

### 2. Vertical Format (.vert)

**Best for:** Corpus query tools (CQPweb, Sketch Engine)

One token per line, structured format:

```
<speech id="11-2_speech_000001" speaker="The DUKE of SUTHERLAND." house="HOUSE OF LORDS" date="1834-02-04">
<s>
The	the	DET	DT
DUKE	duke	NOUN	NN
of	of	ADP	IN
SUTHERLAND	Sutherland	PROPN	NNP
moved	move	VERB	VBD
...
</s>
</speech>
```

**Use with:**
- [CQPweb](http://cwb.sourceforge.net/cqpweb.php) - Web-based corpus analysis
- [Sketch Engine](https://www.sketchengine.eu/) - Commercial corpus tool
- [NoSketch Engine](https://nlp.fi.muni.cz/trac/noske) - Open-source alternative

### 3. TEI XML (.xml)

**Best for:** Digital humanities, archival, publication

Standard XML format for scholarly text encoding:

```xml
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>British Parliamentary Debates, 1834 (Volume 11-2)</title>
      </titleStmt>
      ...
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <div type="speech" xml:id="11-2_speech_000001" who="The DUKE of SUTHERLAND." when="1834-02-04">
        <head>ADDRESS TO HIS MAJESTY.</head>
        <s>
          <w lemma="the" pos="DET" msd="DT">The</w>
          <w lemma="duke" pos="NOUN" msd="NN">DUKE</w>
          <w lemma="of" pos="ADP" msd="IN">of</w>
          ...
        </s>
      </div>
    </body>
  </text>
</TEI>
```

**Use with:**
- [XSLT transformations](https://tei-c.org/release/doc/tei-p5-doc/en/html/ST.html)
- [TEI Publisher](https://teipublisher.com/)
- XML databases like [eXist-db](http://exist-db.org/)

### 4. Annotated JSON (.jsonl)

**Best for:** Custom analysis, machine learning, Python/JavaScript

JSON Lines format with full annotations:

```json
{
  "id": "11-2_speech_000001",
  "house": "HOUSE OF LORDS",
  "date_iso": "1834-02-04",
  "speaker": "The DUKE of SUTHERLAND.",
  "debate_title": "ADDRESS TO HIS MAJESTY.",
  "text": "The DUKE of SUTHERLAND moved...",
  "sentences": [
    {
      "text": "The DUKE of SUTHERLAND moved an Address to his Majesty.",
      "tokens": [
        {
          "id": 1,
          "form": "The",
          "lemma": "the",
          "upos": "DET",
          "xpos": "DT",
          "feats": "Definite=Def|PronType=Art",
          "head": 2,
          "deprel": "det"
        },
        ...
      ]
    }
  ],
  "entities": [
    {"text": "DUKE of SUTHERLAND", "label": "PERSON", "start": 4, "end": 22},
    {"text": "Majesty", "label": "PERSON", "start": 45, "end": 52}
  ],
  "token_count": 234,
  "sentence_count": 8
}
```

**Use with:**
- Python: `json` library
- pandas: `pd.read_json(lines=True)`
- Any programming language

## Example Analyses

### 1. Query POS Tags (Python)

```python
import json

# Count all verbs
verb_count = 0
with open('corpus_output/parliamentary-1834-annotated.jsonl') as f:
    for line in f:
        speech = json.loads(line)
        for sentence in speech['sentences']:
            for token in sentence['tokens']:
                if token['upos'] == 'VERB':
                    verb_count += 1

print(f"Total verbs: {verb_count}")
```

### 2. Extract Named Entities

```python
import json
from collections import Counter

# Find most mentioned people
people = Counter()

with open('corpus_output/parliamentary-1834-annotated.jsonl') as f:
    for line in f:
        speech = json.loads(line)
        for entity in speech['entities']:
            if entity['label'] == 'PERSON':
                people[entity['text']] += 1

# Top 10 most mentioned
for person, count in people.most_common(10):
    print(f"{person}: {count}")
```

### 3. Lemma Frequency

```python
import json
from collections import Counter

lemmas = Counter()

with open('corpus_output/parliamentary-1834-annotated.jsonl') as f:
    for line in f:
        speech = json.loads(line)
        for sentence in speech['sentences']:
            for token in sentence['tokens']:
                if token['upos'] in ['NOUN', 'VERB', 'ADJ']:  # Content words
                    lemmas[token['lemma']] += 1

# Top 20 content words
for lemma, count in lemmas.most_common(20):
    print(f"{lemma}: {count}")
```

## Alternative: Using Stanza (Stanford NLP)

If you prefer Stanza over spaCy (potentially better for historical texts):

```bash
pip install stanza
```

```python
import stanza

# Download English model
stanza.download('en')

# Initialize
nlp = stanza.Pipeline('en')

# Process text
doc = nlp("The DUKE of SUTHERLAND moved an Address.")

# Access annotations
for sentence in doc.sentences:
    for word in sentence.words:
        print(f"{word.text}\t{word.lemma}\t{word.upos}")
```

## Performance Notes

**Full corpus (~21,000 speeches, ~5.5M tokens):**

| Model | Speed | Time Estimate |
|-------|-------|---------------|
| en_core_web_sm | ~10,000 tokens/sec | ~10 min |
| en_core_web_md | ~8,000 tokens/sec | ~12 min |
| en_core_web_lg | ~6,000 tokens/sec | ~15 min |
| en_core_web_trf | ~1,000 tokens/sec | ~90 min |

**Recommendations:**
- Use `--sample 100` for testing (processes in ~30 seconds)
- Run overnight for transformer model on full corpus
- Large model (`lg`) is best balance for production

## Troubleshooting

### "Model not found" error

```bash
python -m spacy download en_core_web_lg
```

### Memory issues with large corpus

Process in batches:

```bash
# Process first 5000 speeches
python create_annotated_corpus.py --sample 5000 --output-dir batch1

# Process next 5000 (modify script to skip first 5000)
python create_annotated_corpus.py --sample 10000 --output-dir batch2
```

### Slow processing

Use smaller model or process in parallel (split speeches file).

## Further Reading

- **spaCy**: https://spacy.io/usage/linguistic-features
- **Universal Dependencies**: https://universaldependencies.org/
- **TEI Guidelines**: https://tei-c.org/guidelines/
- **CoNLL-U format**: https://universaldependencies.org/format.html
- **CQPweb**: http://cwb.sourceforge.net/cqpweb.php

## Next Steps

Once you have your annotated corpus:

1. **Corpus linguistics**: Use CQPweb or Sketch Engine for concordancing
2. **Statistical analysis**: Export to R or Python for quantitative studies
3. **Digital humanities**: Use TEI XML for scholarly editions
4. **Machine learning**: Train models on historical parliamentary language
5. **Comparative studies**: Compare with modern parliamentary corpora

---

**Questions?** The script includes detailed comments and can be customized for specific research needs.
