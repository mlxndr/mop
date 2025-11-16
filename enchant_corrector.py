#!/usr/bin/env python3
"""
Hybrid OCR spell checker using pyenchant + corpus frequency validation.

Two-stage validation:
1. Dictionary check (enchant): Is this word misspelled?
2. Corpus frequency check: Does the correction appear in this corpus?

This prevents false positives while catching real OCR errors.
"""

import json
import re
import enchant
from collections import Counter
from typing import Dict, List, Tuple, Set
import time


class HybridSpellChecker:
    def __init__(self, ocr_file: str):
        self.ocr_file = ocr_file
        self.dict = enchant.Dict("en_GB")  # British English for 1834 Parliament
        self.word_counts = Counter()
        self.corrections_applied = []
        self.words_checked = 0
        self.words_invalid = 0

        # Historical spellings commonly found in 1834 texts
        # Add these to the dictionary so they're not flagged as errors
        historical_spellings = [
            "connexion", "connexions",  # connection/connections
            "shew", "shewed", "shewn",  # show/showed/shown
            "compleat", "compleated",   # complete/completed
            "chuse", "chusing",         # choose/choosing
        ]

        # Proper nouns (people, places) from 1834 parliamentary records
        # Iteration 1: Top false positives identified from initial run
        proper_nouns = [
            "Freeling",      # Sir Francis Freeling (Post Office Secretary)
            "Frome",         # Frome, Somerset (town)
            "Dacre",         # Lord Dacre (title)
            "Bourne",        # Mr. Sturges Bourne (surname)
            "Tanworth",      # Electoral constituency
            "Willington",    # Mr. Willington (surname)
            # Iteration 2
            "Arle",          # Tithing/area in Cheltenham, Gloucester
            "Carleton",      # Place name in Wales
            "Brough",        # Town in England
            "Tennant",       # Surname (Mr. Tennant, Mr. Emerson Tennant)
            # Iteration 3
            "Maryborough",   # Town in Ireland (now Port Laoise)
            "Swanton",       # Villages in Norfolk (Swanton Morley, etc.)
            "Campion",       # Surname (Mr. Campion, magistrate)
        ]

        # Add all whitelisted words
        for word in historical_spellings + proper_nouns:
            self.dict.add(word)

        print(f"✓ Initialized hybrid spell checker with en_GB dictionary")
        print(f"✓ Added {len(historical_spellings)} historical spellings to whitelist")
        print(f"✓ Added {len(proper_nouns)} proper nouns to whitelist (Iterations 1-3)")

    def build_corpus_frequency(self, pages: List[dict]) -> None:
        """Build word frequency dictionary from the entire corpus."""
        print("\nBuilding corpus frequency dictionary...")

        for page in pages:
            text = page.get('markdown', '')
            # Extract words (alphanumeric, keeping hyphens within words)
            words = re.findall(r'\b[A-Za-z](?:[A-Za-z\-\']*[A-Za-z])?\b', text)
            self.word_counts.update(words)

        print(f"✓ Built frequency dictionary: {len(self.word_counts)} unique words")
        print(f"  Total word occurrences: {sum(self.word_counts.values()):,}")

    def get_correction(self, word: str) -> Tuple[str, float]:
        """
        Get correction for a word with confidence score.

        Returns:
            (corrected_word, confidence) where confidence is 0.0-1.0
            Returns (word, 0.0) if no correction needed/possible
        """
        self.words_checked += 1

        # Check if word is valid according to dictionary
        if self.dict.check(word):
            return (word, 0.0)

        self.words_invalid += 1

        # Get suggestions from enchant
        suggestions = self.dict.suggest(word)

        if not suggestions:
            return (word, 0.0)  # No suggestions available

        top_suggestion = suggestions[0]

        # Check if suggestion appears in corpus
        # We check both exact case and lowercase to handle proper nouns
        suggestion_count = self.word_counts.get(top_suggestion, 0)
        suggestion_count_lower = self.word_counts.get(top_suggestion.lower(), 0)
        total_suggestion_count = suggestion_count + suggestion_count_lower

        original_count = self.word_counts.get(word, 0)

        # Calculate confidence based on:
        # 1. How common the suggestion is in corpus
        # 2. How rare the original word is
        # 3. Edit distance (closer = higher confidence)

        if total_suggestion_count == 0:
            # Suggestion doesn't appear in corpus - probably wrong for this context
            return (word, 0.0)

        # Calculate edit distance (Levenshtein)
        edit_dist = self._edit_distance(word.lower(), top_suggestion.lower())

        # Confidence scoring
        confidence = 0.0

        # High corpus frequency for suggestion = good
        if total_suggestion_count >= 100:
            confidence += 0.4
        elif total_suggestion_count >= 10:
            confidence += 0.3
        elif total_suggestion_count >= 3:
            confidence += 0.2
        else:
            confidence += 0.1

        # Low/zero corpus frequency for original = likely error
        if original_count == 0:
            confidence += 0.3
        elif original_count <= 2:
            confidence += 0.2
        elif original_count <= 5:
            confidence += 0.1

        # Small edit distance = higher confidence
        if edit_dist == 1:
            confidence += 0.3
        elif edit_dist == 2:
            confidence += 0.2
        elif edit_dist == 3:
            confidence += 0.1

        return (top_suggestion, confidence)

    def _edit_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein edit distance between two strings."""
        if len(s1) < len(s2):
            return self._edit_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def correct_text(self, text: str, min_confidence: float = 0.7) -> Tuple[str, List[dict]]:
        """
        Correct OCR errors in text.

        Args:
            text: Text to correct
            min_confidence: Minimum confidence to auto-apply correction (0.0-1.0)

        Returns:
            (corrected_text, corrections_list)
        """
        corrections_in_text = []

        # Split into words while preserving structure
        # Use regex to find word boundaries and keep everything else
        def replace_word(match):
            word = match.group(0)

            # Skip very short words (likely abbreviations or noise)
            if len(word) <= 2:
                return word

            # Skip all-caps words longer than 4 chars (likely headers/acronyms)
            if word.isupper() and len(word) > 4:
                return word

            corrected, confidence = self.get_correction(word)

            if confidence >= min_confidence and corrected != word:
                corrections_in_text.append({
                    'original': word,
                    'correction': corrected,
                    'confidence': round(confidence, 2)
                })
                return corrected

            return word

        corrected_text = re.sub(r'\b[A-Za-z](?:[A-Za-z\-\']*[A-Za-z])?\b', replace_word, text)

        return corrected_text, corrections_in_text

    def process_pages(self, min_confidence: float = 0.7) -> dict:
        """
        Process all pages and apply corrections.

        Returns:
            Dictionary with corrected pages and statistics
        """
        print(f"\nLoading OCR data from {self.ocr_file}...")
        with open(self.ocr_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        pages = data.get('pages', [])
        print(f"✓ Loaded {len(pages)} pages")

        # Build frequency dictionary first
        self.build_corpus_frequency(pages)

        # Process pages
        print(f"\nProcessing pages with spell correction (min confidence: {min_confidence})...")
        start_time = time.time()

        corrected_pages = []
        page_corrections = {}

        for i, page in enumerate(pages):
            if i % 500 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                print(f"  Processing page {i}/{len(pages)} ({rate:.1f} pages/sec)")

            original_markdown = page.get('markdown', '')
            corrected_markdown, corrections = self.correct_text(original_markdown, min_confidence)

            corrected_page = page.copy()
            corrected_page['markdown'] = corrected_markdown
            corrected_pages.append(corrected_page)

            if corrections:
                page_corrections[page.get('index', i)] = corrections
                self.corrections_applied.extend(corrections)

        elapsed = time.time() - start_time
        rate = len(pages) / elapsed

        print(f"\n✓ Processed {len(pages)} pages in {elapsed:.1f}s ({rate:.1f} pages/sec)")
        print(f"  Words checked: {self.words_checked:,}")
        print(f"  Words flagged as invalid by dictionary: {self.words_invalid:,}")
        print(f"  Corrections applied: {len(self.corrections_applied):,}")

        # Prepare output data
        output_data = data.copy()
        output_data['pages'] = corrected_pages

        return {
            'data': output_data,
            'corrections': page_corrections,
            'stats': {
                'pages_processed': len(pages),
                'words_checked': self.words_checked,
                'words_invalid': self.words_invalid,
                'corrections_applied': len(self.corrections_applied),
                'processing_time': elapsed,
                'pages_per_second': rate
            }
        }

    def get_correction_summary(self) -> dict:
        """Get summary of corrections by type."""
        correction_types = Counter()

        for correction in self.corrections_applied:
            key = f"{correction['original']} → {correction['correction']}"
            correction_types[key] += 1

        return {
            'total_corrections': len(self.corrections_applied),
            'unique_correction_types': len(correction_types),
            'top_corrections': correction_types.most_common(50)
        }


def main():
    import sys

    # Configuration
    input_file = 'mirror-ocr-11-2-ALL-pages.json'
    output_file = 'mirror-ocr-11-2-ALL-pages-corrected-enchant.json'
    report_file = 'mirror-ocr-11-2-ALL-pages-corrected-enchant-report.json'
    min_confidence = 0.7  # Auto-apply corrections with 70%+ confidence

    print("=" * 70)
    print("HYBRID OCR SPELL CHECKER")
    print("=" * 70)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"Report: {report_file}")
    print(f"Min confidence threshold: {min_confidence}")
    print("=" * 70)

    # Initialize checker
    checker = HybridSpellChecker(input_file)

    # Process pages
    result = checker.process_pages(min_confidence=min_confidence)

    # Save corrected data
    print(f"\nSaving corrected data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result['data'], f, ensure_ascii=False)
    print(f"✓ Saved corrected OCR data")

    # Generate summary
    summary = checker.get_correction_summary()

    # Save report
    print(f"\nSaving report to {report_file}...")
    report = {
        'statistics': result['stats'],
        'summary': summary,
        'top_50_corrections': [
            {
                'correction': corr,
                'count': count
            }
            for corr, count in summary['top_corrections']
        ]
    }

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved correction report")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Pages processed:        {result['stats']['pages_processed']:,}")
    print(f"Words checked:          {result['stats']['words_checked']:,}")
    print(f"Invalid words found:    {result['stats']['words_invalid']:,}")
    print(f"Corrections applied:    {result['stats']['corrections_applied']:,}")
    print(f"Unique correction types: {summary['unique_correction_types']:,}")
    print(f"Processing speed:       {result['stats']['pages_per_second']:.1f} pages/sec")
    print("=" * 70)

    # Show top corrections
    print("\nTop 20 corrections:")
    for i, (correction, count) in enumerate(summary['top_corrections'][:20], 1):
        print(f"  {i:2}. {correction:40} ({count:3}x)")

    print("\n✓ Done!")


if __name__ == '__main__':
    main()
