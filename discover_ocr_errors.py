#!/usr/bin/env python3
"""
Discover actual OCR errors in the parliamentary data
Analyze word frequencies and patterns to find real errors
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

def load_pages(json_path, sample_size=None):
    """Load pages from JSON file"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pages = data.get('pages', [])
    if sample_size:
        pages = pages[:sample_size]

    return pages

def extract_words(pages):
    """Extract all words with their frequencies"""
    word_counts = Counter()

    for page in pages:
        markdown = page.get('markdown', '')
        words = re.findall(r'\b[A-Za-z]+\b', markdown)
        word_counts.update(words)

    return word_counts

def levenshtein_distance(s1, s2):
    """Calculate edit distance between two strings"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
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

def build_high_frequency_dictionary(word_counts, min_frequency=10):
    """Build dictionary from high-frequency words (likely correct)"""
    return {word.lower() for word, count in word_counts.items() if count >= min_frequency}

def find_rare_words(word_counts, max_frequency=3):
    """Find rare words that might be OCR errors"""
    return {word: count for word, count in word_counts.items() if count <= max_frequency}

def find_similar_words(word, dictionary_by_first_letter, max_distance=2):
    """Find words in dictionary similar to given word - OPTIMIZED"""
    word_lower = word.lower()
    candidates = []

    # Only check words starting with similar letters
    first_letter = word_lower[0]
    possible_first_letters = set()

    # Check same letter and adjacent letters
    for offset in range(-2, 3):
        try:
            letter = chr(ord(first_letter) + offset)
            if 'a' <= letter <= 'z':
                possible_first_letters.add(letter)
        except:
            pass

    checked = 0
    max_checks = 500  # Limit comparisons per word

    for letter in possible_first_letters:
        if letter not in dictionary_by_first_letter:
            continue

        for dict_word in dictionary_by_first_letter[letter]:
            if checked >= max_checks:
                break

            # Quick filters
            if abs(len(dict_word) - len(word_lower)) > max_distance:
                continue

            checked += 1
            dist = levenshtein_distance(word_lower, dict_word)
            if dist <= max_distance and dist > 0:
                candidates.append((dict_word, dist))

    return sorted(candidates, key=lambda x: x[1])[:5]  # Only return top 5

def analyze_error_patterns(error_candidates):
    """Analyze common character substitution patterns"""
    patterns = Counter()

    for rare_word, similar_words, rare_count in error_candidates:
        if not similar_words:
            continue

        # Compare with most similar word
        correct_word = similar_words[0][0]

        # Find character differences
        if len(rare_word) == len(correct_word):
            for i, (c1, c2) in enumerate(zip(rare_word.lower(), correct_word)):
                if c1 != c2:
                    patterns[(c1, c2)] += 1

        # Track substring patterns
        for i in range(len(rare_word) - 1):
            bigram_rare = rare_word[i:i+2].lower()
            for j in range(len(correct_word) - 1):
                bigram_correct = correct_word[j:j+2]
                if bigram_rare != bigram_correct and rare_word.lower().count(bigram_rare) == correct_word.count(bigram_correct):
                    patterns[(bigram_rare, bigram_correct)] += 1

    return patterns

def main():
    print("=== OCR Error Discovery Tool ===\n")

    # Load data
    print("Loading data...")
    pages = load_pages('mirror-ocr-11-2-ALL-pages-parsed.json')
    print(f"✓ Loaded {len(pages)} pages\n")

    # Extract word frequencies
    print("Analyzing word frequencies...")
    word_counts = extract_words(pages)
    total_words = sum(word_counts.values())
    unique_words = len(word_counts)
    print(f"✓ Total words: {total_words:,}")
    print(f"✓ Unique words: {unique_words:,}\n")

    # Build high-frequency dictionary (words appearing 10+ times are probably correct)
    print("Building high-frequency dictionary...")
    high_freq_dict = build_high_frequency_dictionary(word_counts, min_frequency=10)
    print(f"✓ High-frequency words (10+ occurrences): {len(high_freq_dict):,}\n")

    # Index dictionary by first letter for faster lookups
    print("Indexing dictionary by first letter...")
    dict_by_first_letter = defaultdict(list)
    for word in high_freq_dict:
        dict_by_first_letter[word[0]].append(word)
    print(f"✓ Indexed {len(dict_by_first_letter)} letter groups\n")

    # Find rare words (potential OCR errors)
    print("Finding rare words (potential errors)...")
    rare_words = find_rare_words(word_counts, max_frequency=3)
    print(f"✓ Rare words (1-3 occurrences): {len(rare_words):,}\n")

    # Find error candidates
    print("Analyzing error candidates...")
    error_candidates = []

    for i, (rare_word, rare_count) in enumerate(rare_words.items()):
        if i % 500 == 0 and i > 0:
            print(f"  Analyzed {i}/{len(rare_words)} rare words...")

        # Skip very short words
        if len(rare_word) < 4:
            continue

        # Skip all caps (likely acronyms or proper nouns)
        if rare_word.isupper() and len(rare_word) > 2:
            continue

        # Find similar high-frequency words
        similar = find_similar_words(rare_word, dict_by_first_letter, max_distance=2)

        if similar:
            # Check if similar word is much more common
            most_similar, distance = similar[0]
            similar_count = word_counts.get(most_similar, 0) + word_counts.get(most_similar.capitalize(), 0)

            # If similar word appears 10+ times more often, likely an error
            if similar_count >= rare_count * 10:
                error_candidates.append((rare_word, similar, rare_count))

    print(f"✓ Found {len(error_candidates)} likely OCR errors\n")

    # Analyze patterns
    print("Analyzing character substitution patterns...")
    patterns = analyze_error_patterns(error_candidates)
    print(f"✓ Found {len(patterns)} substitution patterns\n")

    # Write results
    print("=== Results ===\n")

    print("Top 50 Likely OCR Errors:")
    print("-" * 80)
    for rare_word, similar_words, rare_count in sorted(error_candidates, key=lambda x: x[2], reverse=True)[:50]:
        if similar_words:
            correct_word, distance = similar_words[0]
            correct_count = word_counts.get(correct_word, 0) + word_counts.get(correct_word.capitalize(), 0)
            print(f"{rare_word:20s} → {correct_word:20s} (appears {rare_count}x, correct appears {correct_count}x, dist={distance})")

    print("\n\nTop 30 Character Substitution Patterns:")
    print("-" * 80)
    for (wrong, right), count in patterns.most_common(30):
        print(f"{wrong:15s} → {right:15s} ({count} occurrences)")

    # Save detailed report
    report = {
        'total_words': total_words,
        'unique_words': unique_words,
        'high_frequency_words': len(high_freq_dict),
        'rare_words': len(rare_words),
        'error_candidates': [
            {
                'rare_word': rare_word,
                'suggested_correction': similar_words[0][0] if similar_words else None,
                'rare_count': rare_count,
                'correct_count': word_counts.get(similar_words[0][0], 0) if similar_words else 0,
                'edit_distance': similar_words[0][1] if similar_words else None
            }
            for rare_word, similar_words, rare_count in error_candidates
        ],
        'substitution_patterns': [
            {'wrong': wrong, 'right': right, 'count': count}
            for (wrong, right), count in patterns.most_common(100)
        ]
    }

    with open('ocr-error-analysis.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n\n✓ Saved detailed report to: ocr-error-analysis.json")

if __name__ == '__main__':
    main()
