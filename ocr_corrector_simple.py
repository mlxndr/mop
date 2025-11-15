#!/usr/bin/env python3
"""
Simple OCR Corrector - Character Confusion Patterns Only
Focuses on high-confidence OCR error patterns without dictionary dependence.
"""

import json
import re
import time
from collections import Counter
from pathlib import Path

# Character confusion patterns - common OCR errors
CONFUSION_PATTERNS = {
    # Pattern -> Replacement (only if result looks better)
    "DUEX": "DUKE",
    "rn": "m",
    "cl": "d",
    "vv": "w",
    "aud": "and",
    "aad": "and",
    "tiie": "the",
    "tlie": "the",
    "bnt": "but",
    "iu": "in",
    "thau": "than",
    "cau": "can",
    "wheu": "when",
    "theu": "then",
    "rnost": "most",
    "raay": "may",
    "couutry": "country",
    "ou": "on",  # Context dependent - be careful
    "aud": "and",
    "LOEDS": "LORDS",
    "COUONS": "COMMONS",
}

class SimpleOCRCorrector:
    """Simple pattern-based OCR corrector"""

    def __init__(self):
        self.patterns = CONFUSION_PATTERNS
        self.corrections_made = Counter()

    def correct_word(self, word: str) -> tuple[str, float]:
        """Try to correct a single word, return (corrected, confidence)"""
        original = word

        # Try exact matches first (case sensitive)
        if word in self.patterns:
            return (self.patterns[word], 0.95)

        # Try case-insensitive for all-caps words
        if word.isupper() and word in [k.upper() for k in self.patterns.keys()]:
            for pattern, replacement in self.patterns.items():
                if word == pattern.upper():
                    return (replacement.upper(), 0.95)

        # Try substring replacements (more risky)
        best_correction = word
        best_confidence = 0.0

        for pattern, replacement in self.patterns.items():
            if pattern in word and len(pattern) >= 3:  # Only patterns 3+ chars
                corrected = word.replace(pattern, replacement)
                if corrected != word:
                    confidence = 0.85
                    if confidence > best_confidence:
                        best_correction = corrected
                        best_confidence = confidence

        if best_confidence > 0:
            return (best_correction, best_confidence)

        return (word, 0.0)

    def correct_text(self, text: str, threshold: float = 0.90) -> str:
        """Correct all words in text above confidence threshold"""
        # Find all words
        def replace_word(match):
            word = match.group(0)
            corrected, confidence = self.correct_word(word)

            if confidence >= threshold and corrected != word:
                self.corrections_made[(word, corrected)] += 1
                return corrected
            return word

        # Replace words while preserving positions
        return re.sub(r'\b[A-Za-z]+\b', replace_word, text)

    def process_file(self, input_path: str, output_path: str, sample: int = None):
        """Process JSON file and write corrected version"""
        print(f"\n=== Simple OCR Corrector ===")
        print(f"Input: {input_path}")
        print(f"Output: {output_path}\n")

        # Load
        print("Loading...")
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        pages = data.get('pages', [])
        total_pages = len(pages)

        if sample:
            pages = pages[:sample]
            print(f"Processing {len(pages)} of {total_pages} pages (sample mode)\n")
        else:
            print(f"Processing {total_pages} pages\n")

        # Process
        print("Correcting pages...")
        start_time = time.time()

        for i, page in enumerate(pages):
            if i % 100 == 0 and i > 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                eta = (len(pages) - i) / rate
                print(f"  Page {i}/{len(pages)} ({rate:.1f} pages/sec, ETA: {eta/60:.1f} min)")

            # Correct the markdown
            if 'markdown' in page:
                page['markdown'] = self.correct_text(page['markdown'])

        elapsed = time.time() - start_time
        print(f"\n✓ Processed {len(pages)} pages in {elapsed:.1f}s ({len(pages)/elapsed:.1f} pages/sec)\n")

        # Report corrections
        print("=== Corrections Made ===")
        total_corrections = sum(self.corrections_made.values())
        print(f"Total: {total_corrections} corrections\n")

        if self.corrections_made:
            print("Top corrections:")
            for (original, corrected), count in self.corrections_made.most_common(20):
                print(f"  {original:20s} → {corrected:20s} ({count:3d}x)")
        else:
            print("  No high-confidence corrections found")

        # Write
        print(f"\n=== Writing Output ===")
        data['pages'] = pages
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Wrote: {output_path}")

        # Write report
        report_path = output_path.replace('.json', '-report.json')
        report = {
            'total_pages_processed': len(pages),
            'total_corrections': total_corrections,
            'corrections_by_type': [
                {'original': orig, 'corrected': corr, 'count': count}
                for (orig, corr), count in self.corrections_made.most_common()
            ]
        }
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"✓ Wrote report: {report_path}")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Simple OCR Corrector (Pattern-Based)')
    parser.add_argument('--input', default='mirror-ocr-11-2-ALL-pages-parsed.json')
    parser.add_argument('--output', default='mirror-ocr-11-2-ALL-pages-corrected.json')
    parser.add_argument('--sample', type=int, help='Process only first N pages')

    args = parser.parse_args()

    corrector = SimpleOCRCorrector()
    corrector.process_file(args.input, args.output, args.sample)

if __name__ == '__main__':
    main()
