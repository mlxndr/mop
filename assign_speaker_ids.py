#!/usr/bin/env python3
"""
Speaker ID Assignment for 1834 UK Parliamentary Corpus

Creates unique IDs for speakers and handles:
- Name normalization (case, punctuation, titles)
- Fuzzy matching for similar names
- Title variations (Mr./Sir/Lord/Earl/Duke)
- Multiple people with same surname
- Manual review workflow for ambiguous cases

Outputs:
1. speaker_registry.json - Canonical list of unique speakers with IDs
2. speeches_with_speaker_ids.jsonl - Original speeches + speaker_id field
3. speaker_stats.json - Statistics per speaker (speech count, word count, etc.)
4. ambiguous_speakers.json - Cases needing manual review
"""

import json
import re
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
from pathlib import Path


class SpeakerIDAssigner:
    def __init__(self):
        self.speaker_registry = {}  # canonical_name -> speaker_id
        self.speaker_metadata = {}  # speaker_id -> metadata
        self.name_variations = defaultdict(set)  # speaker_id -> set of name variations
        self.ambiguous_cases = []
        self.next_id = 1

        # Common titles for normalization
        self.titles = [
            'THE', 'Mr.', 'Mr', 'Mrs.', 'Mrs', 'Miss', 'Sir', 'Lord', 'Lady',
            'Earl', 'Duke', 'Duchess', 'Marquess', 'Viscount', 'Baron',
            'Right Honourable', 'Honourable', 'Hon.', 'Rev.', 'Dr.', 'Captain',
            'Colonel', 'Major', 'General', 'Admiral'
        ]

        # Functional titles (not personal names)
        self.functional_titles = {
            'The SPEAKER', 'The CHAIRMAN', 'The CHANCELLOR', 'The CLERK',
            'The LORD CHANCELLOR', 'The ATTORNEY GENERAL', 'The SOLICITOR GENERAL',
            'The SECRETARY', 'The TREASURER', 'The PRESIDENT'
        }

        self.stats = {
            'total_speeches': 0,
            'unique_speakers': 0,
            'name_variations': 0,
            'ambiguous_cases': 0
        }

    def normalize_name(self, name: str) -> str:
        """
        Normalize a speaker name for comparison.

        Examples:
            "The DUKE of SUTHERLAND." -> "Duke of Sutherland"
            "Mr. ROBERT WALLACE" -> "Robert Wallace"
            "Sir Francis Freeling" -> "Francis Freeling"
        """
        if not name:
            return "Unknown"

        # Remove trailing punctuation
        name = name.rstrip('.,;:')

        # Remove "The" prefix
        name = re.sub(r'^[Tt]he\s+', '', name)

        # Normalize case (Title Case for comparison)
        name = name.title()

        # Remove honorifics but keep substantive titles
        # Keep: Duke, Earl, Lord (part of identity)
        # Remove: Mr., Sir, Hon. (just honorifics)
        honorifics = ['Mr.', 'Mr', 'Mrs.', 'Mrs', 'Miss', 'Sir', 'Hon.', 'Honourable']
        for honorific in honorifics:
            name = re.sub(rf'\b{re.escape(honorific)}\s+', '', name, flags=re.IGNORECASE)

        # Normalize whitespace
        name = ' '.join(name.split())

        return name

    def extract_surname(self, normalized_name: str) -> str:
        """
        Extract the likely surname from a normalized name.

        Examples:
            "Duke of Sutherland" -> "Sutherland"
            "Robert Wallace" -> "Wallace"
            "Earl of Essex" -> "Essex"
        """
        # Handle "X of Y" pattern (nobility)
        if ' of ' in normalized_name.lower():
            parts = normalized_name.lower().split(' of ')
            return parts[-1].strip().title()

        # Take last word as surname
        parts = normalized_name.split()
        if parts:
            return parts[-1]

        return normalized_name

    def similarity_score(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names (0.0 to 1.0).

        Uses SequenceMatcher for fuzzy matching to catch OCR errors.
        """
        return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

    def is_functional_title(self, name: str) -> bool:
        """Check if this is a functional title rather than a person."""
        normalized = self.normalize_name(name)
        return normalized in self.functional_titles

    def find_matching_speaker(self, name: str, threshold: float = 0.85) -> Optional[str]:
        """
        Find existing speaker ID that matches this name.

        Returns:
            speaker_id if match found, None otherwise
        """
        normalized = self.normalize_name(name)

        # Exact match in registry
        if normalized in self.speaker_registry:
            return self.speaker_registry[normalized]

        # Check known variations
        for speaker_id, variations in self.name_variations.items():
            if normalized in variations:
                return speaker_id

        # Fuzzy match based on surname
        surname = self.extract_surname(normalized)
        candidates = []

        for existing_name, speaker_id in self.speaker_registry.items():
            existing_surname = self.extract_surname(existing_name)

            # If surnames match exactly, check full name similarity
            if surname.lower() == existing_surname.lower():
                similarity = self.similarity_score(normalized, existing_name)
                if similarity >= threshold:
                    candidates.append((speaker_id, existing_name, similarity))

        # If we found matches, return the best one
        if candidates:
            candidates.sort(key=lambda x: x[2], reverse=True)
            best_match = candidates[0]

            # If multiple good matches, flag as ambiguous
            if len(candidates) > 1 and candidates[1][2] >= threshold:
                self.ambiguous_cases.append({
                    'new_name': name,
                    'normalized': normalized,
                    'candidates': [
                        {'speaker_id': c[0], 'name': c[1], 'similarity': c[2]}
                        for c in candidates
                    ]
                })
                self.stats['ambiguous_cases'] += 1

            return best_match[0]

        return None

    def assign_speaker_id(self, name: str, house: str, date: str) -> str:
        """
        Assign a unique speaker ID, creating new if necessary.

        Returns:
            speaker_id (e.g., "SPEAKER_001", "SPEAKER_002", etc.)
        """
        # Handle functional titles
        if self.is_functional_title(name):
            normalized = self.normalize_name(name)
            if normalized not in self.speaker_registry:
                speaker_id = f"FUNCTIONAL_{self.next_id:04d}"
                self.next_id += 1
                self.speaker_registry[normalized] = speaker_id
                self.speaker_metadata[speaker_id] = {
                    'canonical_name': normalized,
                    'type': 'functional_title',
                    'first_seen': date,
                    'houses': {house}
                }
            return self.speaker_registry[normalized]

        # Try to find existing speaker
        existing_id = self.find_matching_speaker(name)

        if existing_id:
            # Update variations
            normalized = self.normalize_name(name)
            self.name_variations[existing_id].add(normalized)
            self.name_variations[existing_id].add(name)  # Original form too

            # Update metadata
            if house not in self.speaker_metadata[existing_id]['houses']:
                self.speaker_metadata[existing_id]['houses'].add(house)

            self.stats['name_variations'] += 1
            return existing_id

        # Create new speaker
        speaker_id = f"SPEAKER_{self.next_id:04d}"
        self.next_id += 1

        normalized = self.normalize_name(name)
        self.speaker_registry[normalized] = speaker_id
        self.name_variations[speaker_id].add(normalized)
        self.name_variations[speaker_id].add(name)

        self.speaker_metadata[speaker_id] = {
            'canonical_name': normalized,
            'type': 'person',
            'first_seen': date,
            'houses': {house}
        }

        self.stats['unique_speakers'] += 1
        return speaker_id

    def process_speeches(self, speeches_file: str) -> List[Dict]:
        """
        Process all speeches and assign speaker IDs.

        Returns:
            List of speeches with speaker_id added
        """
        print(f"Loading speeches from {speeches_file}...")

        speeches = []
        with open(speeches_file, 'r', encoding='utf-8') as f:
            for line in f:
                speeches.append(json.loads(line))

        print(f"✓ Loaded {len(speeches)} speeches")

        # First pass: assign IDs
        print("\nAssigning speaker IDs...")
        for i, speech in enumerate(speeches):
            if i % 1000 == 0:
                print(f"  Processing speech {i+1}/{len(speeches)}...")

            name = speech.get('speaker', 'Unknown')
            house = speech.get('house', 'Unknown')
            date = speech.get('date_iso', 'Unknown')

            speaker_id = self.assign_speaker_id(name, house, date)
            speech['speaker_id'] = speaker_id

            self.stats['total_speeches'] += 1

        return speeches

    def calculate_speaker_stats(self, speeches: List[Dict]) -> Dict:
        """
        Calculate statistics for each speaker.

        Returns:
            Dict mapping speaker_id to stats
        """
        stats = defaultdict(lambda: {
            'speech_count': 0,
            'total_words': 0,
            'houses': set(),
            'dates': [],
            'debates': set()
        })

        for speech in speeches:
            speaker_id = speech['speaker_id']
            text = speech.get('text', '')
            word_count = len(text.split())

            stats[speaker_id]['speech_count'] += 1
            stats[speaker_id]['total_words'] += word_count
            stats[speaker_id]['houses'].add(speech.get('house', 'Unknown'))
            stats[speaker_id]['dates'].append(speech.get('date_iso', 'Unknown'))
            stats[speaker_id]['debates'].add(speech.get('debate_title', 'Unknown'))

        # Convert sets to lists for JSON serialization
        for speaker_id, data in stats.items():
            data['houses'] = sorted(list(data['houses']))
            data['dates'] = sorted(list(set(data['dates'])))
            data['debates'] = list(data['debates'])
            data['date_range'] = {
                'first': min(data['dates']) if data['dates'] else None,
                'last': max(data['dates']) if data['dates'] else None
            }

        return dict(stats)

    def export_speaker_registry(self, output_file: str):
        """
        Export speaker registry to JSON.

        Format:
        {
          "SPEAKER_001": {
            "canonical_name": "Duke of Sutherland",
            "variations": ["The DUKE of SUTHERLAND", "Duke of Sutherland"],
            "type": "person",
            "houses": ["HOUSE OF LORDS"],
            "first_seen": "1834-02-04"
          }
        }
        """
        registry = {}

        for speaker_id, metadata in self.speaker_metadata.items():
            registry[speaker_id] = {
                **metadata,
                'variations': sorted(list(self.name_variations[speaker_id])),
                'houses': sorted(list(metadata['houses']))
            }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)

        print(f"✓ Saved speaker registry: {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Assign unique IDs to speakers in parliamentary corpus"
    )
    parser.add_argument(
        '--input',
        default='11-2-speeches.jsonl',
        help='Input JSONL file with speeches'
    )
    parser.add_argument(
        '--output-speeches',
        default='11-2-speeches-with-ids.jsonl',
        help='Output JSONL with speaker_id added'
    )
    parser.add_argument(
        '--output-registry',
        default='speaker_registry.json',
        help='Output speaker registry JSON'
    )
    parser.add_argument(
        '--output-stats',
        default='speaker_stats.json',
        help='Output speaker statistics JSON'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.85,
        help='Similarity threshold for matching (0.0-1.0)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("SPEAKER ID ASSIGNMENT")
    print("=" * 70)
    print(f"Input: {args.input}")
    print(f"Similarity threshold: {args.threshold}")
    print("=" * 70)

    # Initialize assigner
    assigner = SpeakerIDAssigner()

    # Process speeches
    speeches = assigner.process_speeches(args.input)

    # Calculate stats
    print("\nCalculating speaker statistics...")
    speaker_stats = assigner.calculate_speaker_stats(speeches)

    # Export results
    print("\nExporting results...")

    # Speeches with IDs
    with open(args.output_speeches, 'w', encoding='utf-8') as f:
        for speech in speeches:
            f.write(json.dumps(speech, ensure_ascii=False) + '\n')
    print(f"✓ Saved speeches with IDs: {args.output_speeches}")

    # Speaker registry
    assigner.export_speaker_registry(args.output_registry)

    # Speaker stats
    with open(args.output_stats, 'w', encoding='utf-8') as f:
        json.dump(speaker_stats, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved speaker stats: {args.output_stats}")

    # Ambiguous cases (if any)
    if assigner.ambiguous_cases:
        ambiguous_file = 'ambiguous_speakers.json'
        with open(ambiguous_file, 'w', encoding='utf-8') as f:
            json.dump(assigner.ambiguous_cases, f, indent=2, ensure_ascii=False)
        print(f"⚠️  Saved ambiguous cases: {ambiguous_file}")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total speeches:        {assigner.stats['total_speeches']:,}")
    print(f"Unique speakers:       {assigner.stats['unique_speakers']:,}")
    print(f"Name variations:       {assigner.stats['name_variations']:,}")
    print(f"Ambiguous cases:       {assigner.stats['ambiguous_cases']:,}")
    print("=" * 70)

    # Show top speakers
    print("\nTop 20 speakers by speech count:")
    sorted_speakers = sorted(
        speaker_stats.items(),
        key=lambda x: x[1]['speech_count'],
        reverse=True
    )

    for i, (speaker_id, stats) in enumerate(sorted_speakers[:20], 1):
        canonical = assigner.speaker_metadata[speaker_id]['canonical_name']
        count = stats['speech_count']
        words = stats['total_words']
        print(f"  {i:2}. {speaker_id}: {canonical:40} ({count:4} speeches, {words:,} words)")

    print("\n✓ Done!")


if __name__ == '__main__':
    main()
