#!/usr/bin/env python3
"""
Frequency-Based OCR Corrector
Uses actual error candidates discovered from corpus analysis to fix OCR errors.
"""

import json
import re
import time
from collections import Counter
from pathlib import Path

class FrequencyBasedCorrector:
    """Corrector based on frequency analysis of actual corpus"""

    def __init__(self, error_analysis_path='ocr-error-analysis.json', confidence_threshold=0.85):
        self.confidence_threshold = confidence_threshold
        self.corrections = {}  # rare_word -> (correct_word, confidence)
        self.corrections_made = Counter()

        self._load_error_analysis(error_analysis_path)

    def _load_error_analysis(self, path):
        """Load error analysis and build correction lookup"""
        print(f"Loading error analysis from {path}...")

        with open(path, 'r', encoding='utf-8') as f:
            analysis = json.load(f)

        error_candidates = analysis.get('error_candidates', [])
        print(f"✓ Loaded {len(error_candidates)} error candidates")

        # Build correction lookup with confidence scoring
        print("Building correction lookup...")

        # Track skipped corrections for reporting
        skipped_proper_nouns = 0
        skipped_all_caps = 0

        for candidate in error_candidates:
            rare_word = candidate.get('rare_word')
            correct_word = candidate.get('suggested_correction')
            rare_count = candidate.get('rare_count', 0)
            correct_count = candidate.get('correct_count', 0)
            edit_distance = candidate.get('edit_distance', 999)

            if not rare_word or not correct_word:
                continue

            # IMPORTANT: Skip if rare_word is a proper noun (capitalized)
            # These are likely titles, names, places - not OCR errors
            if len(rare_word) > 1 and rare_word[0].isupper() and rare_word[1:].islower():
                skipped_proper_nouns += 1
                continue

            # Skip all-caps words (likely acronyms, headers)
            if rare_word.isupper() and len(rare_word) > 1:
                skipped_all_caps += 1
                continue

            # Calculate confidence based on:
            # 1. Frequency ratio (how much more common is the correct word)
            # 2. Edit distance (closer = more confident)
            # 3. Absolute frequency (correct word should be reasonably common)

            if correct_count == 0 or rare_count == 0:
                continue

            frequency_ratio = correct_count / rare_count

            # Base confidence on frequency ratio
            if frequency_ratio >= 50:
                confidence = 0.95
            elif frequency_ratio >= 20:
                confidence = 0.90
            elif frequency_ratio >= 10:
                confidence = 0.85
            else:
                confidence = 0.70

            # Adjust for edit distance
            if edit_distance == 1:
                confidence += 0.03
            elif edit_distance == 2:
                confidence += 0.01

            # Penalize if correct word is not very common
            if correct_count < 30:
                confidence -= 0.10

            # Only add if confidence meets threshold
            if confidence >= self.confidence_threshold:
                # Prefer higher confidence if we already have a correction
                if rare_word in self.corrections:
                    existing_conf = self.corrections[rare_word][1]
                    if confidence > existing_conf:
                        self.corrections[rare_word] = (correct_word, confidence)
                else:
                    self.corrections[rare_word] = (correct_word, confidence)

        print(f"✓ Built lookup with {len(self.corrections)} high-confidence corrections (≥{self.confidence_threshold})")
        print(f"  Skipped {skipped_proper_nouns} capitalized proper nouns (titles, names, places)")
        print(f"  Skipped {skipped_all_caps} all-caps words (acronyms, headers)")

        # Show top 20 corrections
        print("\nTop 20 corrections to be applied:")
        sorted_corrections = sorted(
            self.corrections.items(),
            key=lambda x: x[1][1],
            reverse=True
        )[:20]

        for rare_word, (correct_word, conf) in sorted_corrections:
            print(f"  {rare_word:20s} → {correct_word:20s} (confidence: {conf:.2f})")

    def correct_word(self, word: str) -> tuple[str, float]:
        """Try to correct a single word"""
        # Don't correct proper nouns (capitalized words) - they're likely names/titles
        if len(word) > 1 and word[0].isupper() and word[1:].islower():
            return (word, 0.0)

        # Don't correct all-caps words - they're likely acronyms or headers
        if word.isupper() and len(word) > 1:
            return (word, 0.0)

        # Check lowercase match only
        word_lower = word.lower()
        if word_lower in self.corrections:
            correct, conf = self.corrections[word_lower]
            # Preserve original capitalization pattern
            if word[0].isupper():
                correct = correct.capitalize()
            elif word.isupper():
                correct = correct.upper()
            return (correct, conf)

        return (word, 0.0)

    def correct_text(self, text: str, threshold: float = 0.85) -> str:
        """Correct all words in text above confidence threshold"""
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
        print(f"\n=== Frequency-Based OCR Corrector ===")
        print(f"Input: {input_path}")
        print(f"Output: {output_path}")
        print(f"Confidence threshold: {self.confidence_threshold}\n")

        # Load
        print("Loading OCR data...")
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
                total_corrections = sum(self.corrections_made.values())
                print(f"  Page {i}/{len(pages)} ({rate:.1f} pages/sec, ETA: {eta/60:.1f} min, {total_corrections} corrections)")

            # Correct the markdown
            if 'markdown' in page:
                page['markdown'] = self.correct_text(page['markdown'], self.confidence_threshold)

        elapsed = time.time() - start_time
        print(f"\n✓ Processed {len(pages)} pages in {elapsed:.1f}s ({len(pages)/elapsed:.1f} pages/sec)\n")

        # Report corrections
        print("=== Corrections Applied ===")
        total_corrections = sum(self.corrections_made.values())
        print(f"Total: {total_corrections} corrections across {len(self.corrections_made)} unique error types\n")

        if self.corrections_made:
            print("Top 50 corrections applied:")
            for (original, corrected), count in self.corrections_made.most_common(50):
                confidence = self.corrections.get(original, self.corrections.get(original.lower(), (None, 0)))[1]
                print(f"  {original:20s} → {corrected:20s} ({count:3d}x, conf: {confidence:.2f})")
        else:
            print("  No corrections made (threshold may be too high)")

        # Write
        print(f"\n=== Writing Output ===")
        data['pages'] = pages
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Wrote: {output_path}")

        # Write report
        report_path = output_path.replace('.json', '-frequency-report.json')
        report = {
            'total_pages_processed': len(pages),
            'total_corrections': total_corrections,
            'unique_error_types': len(self.corrections_made),
            'confidence_threshold': self.confidence_threshold,
            'available_corrections': len(self.corrections),
            'corrections_by_type': [
                {
                    'original': orig,
                    'corrected': corr,
                    'count': count,
                    'confidence': self.corrections.get(orig, self.corrections.get(orig.lower(), (None, 0)))[1]
                }
                for (orig, corr), count in self.corrections_made.most_common()
            ]
        }
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"✓ Wrote report: {report_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Frequency-Based OCR Corrector')
    parser.add_argument('--input', default='mirror-ocr-11-2-ALL-pages-parsed.json',
                       help='Input OCR JSON file')
    parser.add_argument('--output', default='mirror-ocr-11-2-ALL-pages-corrected-frequency.json',
                       help='Output corrected JSON file')
    parser.add_argument('--analysis', default='ocr-error-analysis.json',
                       help='Error analysis JSON file')
    parser.add_argument('--threshold', type=float, default=0.85,
                       help='Confidence threshold for applying corrections (default: 0.85)')
    parser.add_argument('--sample', type=int, help='Process only first N pages')

    args = parser.parse_args()

    corrector = FrequencyBasedCorrector(args.analysis, args.threshold)
    corrector.process_file(args.input, args.output, args.sample)


if __name__ == '__main__':
    main()
