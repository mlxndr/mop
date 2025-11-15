#!/usr/bin/env python3
"""
Parliamentary OCR Corrector
Implements 6 computational methods to detect and fix OCR errors in historical parliamentary text.
"""

import json
import re
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Tuple, Optional
import math
from pathlib import Path

# Check for required dependencies
try:
    import enchant
except ImportError:
    print("Warning: pyenchant not installed. Using basic dictionary only.")
    enchant = None

try:
    from Levenshtein import distance as levenshtein_distance
except ImportError:
    print("Warning: python-Levenshtein not installed. Using slower fallback.")
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Fallback Levenshtein distance implementation"""
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


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ErrorCandidate:
    """Represents a potential OCR error with suggested corrections"""
    page_index: int
    original_word: str
    position: int  # Character offset in markdown
    error_types: List[str]  # ["unknown_word", "confusion_pattern", etc.]
    suggested_corrections: List[Tuple[str, float]]  # [(word, confidence), ...]
    context: str  # ±50 chars around the word

    def to_dict(self):
        return {
            'page_index': self.page_index,
            'original_word': self.original_word,
            'position': self.position,
            'error_types': self.error_types,
            'context': self.context,
            'suggested_corrections': [
                {'word': w, 'confidence': c} for w, c in self.suggested_corrections
            ]
        }


@dataclass
class NamedEntity:
    """Represents a named entity found in the text"""
    canonical: str  # Most common form
    entity_type: str  # "SPEAKER", "LOCATION", "TITLE"
    occurrences: List[Tuple[int, int]]  # [(page_index, position), ...]
    variants: Set[str]  # Different spellings


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "character_confusion_pairs": {
        # Common OCR errors in historical texts
        "X": ["K"],
        "rn": ["m"],
        "cl": ["d"],
        "vv": ["w"],
        "u": ["n"],
        "ii": ["u"],
        "aud": ["and"],
        "aad": ["and"],
        "cau": ["can"],
        "iu": ["in"],
        "thau": ["than"],
        "aud": ["and"],
        "bnt": ["but"],
        "aud": ["and"],
        "tiie": ["the"],
        "tlie": ["the"],
    },
    "edit_distance_threshold": 2,
    "min_ngram_score": -15.0,
    "auto_correct_threshold": 0.90,
    "preserve_historical_spellings": [
        "connexion", "shew", "shewn", "shewed", "pro formâ",
        "portale", "hostages", "favourable", "colour", "honour",
        "labour", "favour", "endeavour", "neighbour"
    ],
    "structural_patterns": {
        "speaker": r'^(The |LORD |EARL |DUKE |Mr\. |Sir |COLONEL |MAJOR |CAPTAIN )?[A-Z][A-Za-z\s\-]+\.—',
        "house_header": r'^HOUSE OF (LORDS|COMMONS)',
        "date_header": r'^[A-Z]+,\s+\d+°\s+DIE\s+[A-Z]+,\s+\d{4}\.$'
    },
    "data_dir": "data",
    "websters_1828_url": "https://raw.githubusercontent.com/matthewreagan/WebstersEnglishDictionary/master/dictionary.json"
}


# ============================================================================
# BOOTSTRAP DATA
# ============================================================================

class DataBootstrapper:
    """Downloads and creates necessary data files on first run"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def bootstrap_all(self):
        """Bootstrap all necessary data"""
        print("=== Bootstrapping Data ===")

        # 1. Build parliamentary lexicon from speeches
        self.build_parliamentary_lexicon()

        # 2. Download or create historical dictionary
        self.setup_historical_dictionary()

        print("✓ Bootstrap complete\n")

    def build_parliamentary_lexicon(self):
        """Extract proper nouns and terms from speeches file"""
        lexicon_path = self.data_dir / "parliamentary_lexicon.txt"

        if lexicon_path.exists():
            print(f"✓ Parliamentary lexicon already exists: {lexicon_path}")
            return

        print("Building parliamentary lexicon from speeches...")

        if not os.path.exists('11-2-speeches.jsonl'):
            print("Warning: 11-2-speeches.jsonl not found. Skipping parliamentary lexicon.")
            lexicon_path.write_text("")
            return

        terms = set()

        # Extract from speeches
        with open('11-2-speeches.jsonl', 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i % 5000 == 0:
                    print(f"  Processing speech {i}...")
                try:
                    speech = json.loads(line)

                    # Extract speaker names
                    if 'speaker' in speech:
                        speaker = speech['speaker']
                        # Clean and add
                        terms.add(speaker.strip())
                        # Add individual words from speaker
                        for word in re.findall(r'\b[A-Z][a-z]+\b', speaker):
                            terms.add(word)

                    # Extract debate titles
                    if 'debate_title' in speech:
                        for word in re.findall(r'\b[A-Z][A-Z]+\b', speech['debate_title']):
                            terms.add(word)

                    # Extract house
                    if 'house' in speech:
                        terms.add(speech['house'])

                except json.JSONDecodeError:
                    continue

        # Write lexicon
        with open(lexicon_path, 'w', encoding='utf-8') as f:
            for term in sorted(terms):
                f.write(f"{term}\n")

        print(f"✓ Built parliamentary lexicon: {len(terms)} terms")

    def setup_historical_dictionary(self):
        """Download Webster's 1828 or create basic historical wordlist"""
        dict_path = self.data_dir / "websters_1828.txt"

        if dict_path.exists():
            print(f"✓ Historical dictionary already exists: {dict_path}")
            return

        print("Setting up historical dictionary...")

        # Try to download Webster's 1828
        try:
            import urllib.request
            print(f"  Attempting to download from {CONFIG['websters_1828_url']}")

            with urllib.request.urlopen(CONFIG['websters_1828_url'], timeout=10) as response:
                data = json.loads(response.read())

                # Extract words
                words = set()
                if isinstance(data, dict):
                    words = set(data.keys())
                elif isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict) and 'word' in entry:
                            words.add(entry['word'])

                # Write to file
                with open(dict_path, 'w', encoding='utf-8') as f:
                    for word in sorted(words):
                        f.write(f"{word}\n")

                print(f"✓ Downloaded Webster's 1828: {len(words)} words")
                return

        except Exception as e:
            print(f"  Could not download: {e}")

        # Fallback: Create basic historical spelling list
        print("  Creating fallback historical wordlist...")
        historical_words = [
            "shew", "shewn", "shewed", "connexion", "compleat", "publick",
            "musick", "favour", "honour", "colour", "labour", "neighbour",
            "centre", "theatre", "metre", "travelled", "marvellous"
        ]

        with open(dict_path, 'w', encoding='utf-8') as f:
            for word in historical_words:
                f.write(f"{word}\n")

        print(f"✓ Created fallback wordlist: {len(historical_words)} words")


# ============================================================================
# METHOD 1: DICTIONARY-BASED SPELL CHECKING
# ============================================================================

class DictionaryChecker:
    """Check words against multiple dictionaries"""

    def __init__(self, config: dict, data_dir: Path):
        self.config = config
        self.data_dir = Path(data_dir)
        self.modern_dict = None
        self.historical_words = set()
        self.parliamentary_terms = set()
        self.preserved_spellings = set(config['preserve_historical_spellings'])

        self._load_dictionaries()

    def _load_dictionaries(self):
        """Load all dictionaries"""
        # Modern English (via enchant)
        if enchant:
            try:
                self.modern_dict = enchant.Dict("en_US")
                print("✓ Loaded modern English dictionary (en_US)")
            except:
                try:
                    self.modern_dict = enchant.Dict("en_GB")
                    print("✓ Loaded modern English dictionary (en_GB)")
                except:
                    print("Warning: Could not load enchant dictionary")

        # Historical dictionary
        hist_path = self.data_dir / "websters_1828.txt"
        if hist_path.exists():
            with open(hist_path, 'r', encoding='utf-8') as f:
                self.historical_words = {line.strip().lower() for line in f if line.strip()}
            print(f"✓ Loaded historical dictionary: {len(self.historical_words)} words")

        # Parliamentary lexicon
        parl_path = self.data_dir / "parliamentary_lexicon.txt"
        if parl_path.exists():
            with open(parl_path, 'r', encoding='utf-8') as f:
                self.parliamentary_terms = {line.strip() for line in f if line.strip()}
            print(f"✓ Loaded parliamentary lexicon: {len(self.parliamentary_terms)} terms")

    def check_word(self, word: str) -> bool:
        """Check if word is valid in any dictionary"""
        if not word or len(word) < 2:
            return True  # Skip very short words

        # Remove trailing punctuation
        clean_word = word.rstrip('.,;:!?—')

        # Preserve historical spellings
        if clean_word.lower() in self.preserved_spellings:
            return True

        # Check parliamentary terms (exact match)
        if clean_word in self.parliamentary_terms:
            return True

        # Check if it's a number or Roman numeral
        if re.match(r'^\d+$', clean_word) or re.match(r'^[IVXLCDM]+$', clean_word):
            return True

        # Check modern dictionary
        if self.modern_dict:
            try:
                if self.modern_dict.check(clean_word):
                    return True
            except:
                pass

        # Check historical dictionary
        if clean_word.lower() in self.historical_words:
            return True

        return False


# ============================================================================
# METHOD 2: CHARACTER CONFUSION PATTERN DETECTION
# ============================================================================

class ConfusionDetector:
    """Detect and correct character confusion patterns"""

    def __init__(self, config: dict, dict_checker: DictionaryChecker):
        self.confusion_pairs = config['character_confusion_pairs']
        self.dict_checker = dict_checker

    def find_confusion_patterns(self, word: str) -> List[Tuple[str, float]]:
        """Find potential corrections based on character confusion"""
        candidates = []

        for wrong, rights in self.confusion_pairs.items():
            if wrong in word:
                for right in rights:
                    # Generate candidate
                    candidate = word.replace(wrong, right)

                    # Check if candidate is valid
                    if candidate != word and self.dict_checker.check_word(candidate):
                        # Higher confidence for exact case matches
                        confidence = 0.85 if wrong.isupper() == right.isupper() else 0.75
                        candidates.append((candidate, confidence))

        return candidates


# ============================================================================
# METHOD 3: NAMED ENTITY CONSISTENCY VALIDATION
# ============================================================================

class EntityValidator:
    """Extract and validate named entities for consistency"""

    def __init__(self, config: dict):
        self.config = config
        self.entities: Dict[str, NamedEntity] = {}
        self.speaker_pattern = re.compile(config['structural_patterns']['speaker'])

    def extract_entities(self, pages: List[dict]) -> Dict[str, NamedEntity]:
        """Extract all named entities from corpus"""
        print("Extracting named entities...")

        speaker_counts = Counter()
        speaker_positions = defaultdict(list)

        for page in pages:
            markdown = page.get('markdown', '')
            page_idx = page.get('index', 0)

            # Extract speakers
            for match in self.speaker_pattern.finditer(markdown):
                speaker = match.group(0).rstrip('.—')
                speaker_counts[speaker] += 1
                speaker_positions[speaker].append((page_idx, match.start()))

        # Build entities from most common forms
        for speaker, count in speaker_counts.items():
            # Find similar variants
            variants = {s for s in speaker_counts.keys()
                       if levenshtein_distance(s.lower(), speaker.lower()) <= 2}

            # Use most common as canonical
            canonical = max(variants, key=lambda s: speaker_counts[s])

            if canonical not in self.entities:
                self.entities[canonical] = NamedEntity(
                    canonical=canonical,
                    entity_type="SPEAKER",
                    occurrences=speaker_positions[canonical],
                    variants=variants
                )

        print(f"✓ Extracted {len(self.entities)} unique entities")
        return self.entities

    def find_inconsistencies(self, page: dict) -> List[ErrorCandidate]:
        """Find entity inconsistencies in a page"""
        errors = []
        markdown = page.get('markdown', '')
        page_idx = page.get('index', 0)

        for match in self.speaker_pattern.finditer(markdown):
            speaker = match.group(0).rstrip('.—')

            # Check if this is a rare variant
            for canonical, entity in self.entities.items():
                if speaker in entity.variants and speaker != canonical:
                    # This is a variant - suggest canonical
                    variant_count = sum(1 for s in entity.variants)
                    if variant_count > 1:
                        errors.append(ErrorCandidate(
                            page_index=page_idx,
                            original_word=speaker,
                            position=match.start(),
                            error_types=['entity_inconsistency'],
                            suggested_corrections=[(canonical, 0.70)],
                            context=markdown[max(0, match.start()-50):match.end()+50]
                        ))

        return errors


# ============================================================================
# METHOD 4: N-GRAM LANGUAGE MODEL SCORING
# ============================================================================

class NgramScorer:
    """Score word sequences using n-gram probabilities"""

    def __init__(self, pages: List[dict], config: dict):
        self.config = config
        self.unigrams = Counter()
        self.bigrams = Counter()
        self.trigrams = Counter()
        self.total_words = 0

        self._train(pages)

    def _train(self, pages: List[dict]):
        """Train n-gram model on corpus"""
        print("Training n-gram model...")

        for page in pages:
            markdown = page.get('markdown', '')
            words = self._tokenize(markdown)

            self.total_words += len(words)

            # Count unigrams
            self.unigrams.update(words)

            # Count bigrams
            for i in range(len(words) - 1):
                self.bigrams[(words[i], words[i+1])] += 1

            # Count trigrams
            for i in range(len(words) - 2):
                self.trigrams[(words[i], words[i+1], words[i+2])] += 1

        print(f"✓ Trained on {self.total_words} words")
        print(f"  Unigrams: {len(self.unigrams)}, Bigrams: {len(self.bigrams)}, Trigrams: {len(self.trigrams)}")

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        # Keep words with letters
        return re.findall(r'\b[A-Za-z]+\b', text.lower())

    def score_trigram(self, w1: str, w2: str, w3: str) -> float:
        """Calculate log probability of trigram with smoothing"""
        trigram_count = self.trigrams.get((w1, w2, w3), 0)
        bigram_count = self.bigrams.get((w1, w2), 0)

        # Laplace smoothing
        prob = (trigram_count + 1) / (bigram_count + len(self.unigrams))
        return math.log(prob)

    def score_sequence(self, words: List[str]) -> List[Tuple[int, str, float]]:
        """Score sequence and return low-scoring words"""
        low_scores = []

        for i in range(2, len(words)):
            score = self.score_trigram(words[i-2], words[i-1], words[i])
            if score < self.config['min_ngram_score']:
                low_scores.append((i, words[i], score))

        return low_scores


# ============================================================================
# METHOD 5: EDIT DISTANCE CORRECTION
# ============================================================================

class EditDistanceCorrector:
    """Generate corrections using edit distance and context"""

    def __init__(self, config: dict, dict_checker: DictionaryChecker, ngram_scorer: NgramScorer):
        self.config = config
        self.dict_checker = dict_checker
        self.ngram_scorer = ngram_scorer
        self.vocabulary = set()

        # Build vocabulary from n-gram scorer
        self.vocabulary = set(ngram_scorer.unigrams.keys())

    def generate_corrections(self, word: str, context_words: List[str]) -> List[Tuple[str, float]]:
        """Generate correction candidates with confidence scores"""
        candidates = []
        threshold = self.config['edit_distance_threshold']

        # Find words within edit distance
        for vocab_word in self.vocabulary:
            if abs(len(vocab_word) - len(word)) > threshold:
                continue  # Skip if length difference is too large

            dist = levenshtein_distance(word.lower(), vocab_word.lower())
            if dist <= threshold and dist > 0:
                # Calculate confidence
                confidence = self._calculate_confidence(word, vocab_word, context_words, dist)
                candidates.append((vocab_word, confidence))

        # Sort by confidence and return top candidates
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:5]

    def _calculate_confidence(self, original: str, candidate: str, context: List[str], edit_dist: int) -> float:
        """Calculate confidence score for a candidate"""
        score = 0.0

        # Component 1: Dictionary presence (0.4 weight)
        if self.dict_checker.check_word(candidate):
            score += 0.4

        # Component 2: Edit distance (0.3 weight)
        # Closer = better
        score += 0.3 * (1.0 - (edit_dist / self.config['edit_distance_threshold']))

        # Component 3: N-gram context (0.3 weight)
        if len(context) >= 2:
            # Try trigram with context
            original_score = self.ngram_scorer.score_trigram(
                context[-2] if len(context) > 1 else '',
                context[-1] if len(context) > 0 else '',
                original.lower()
            )
            candidate_score = self.ngram_scorer.score_trigram(
                context[-2] if len(context) > 1 else '',
                context[-1] if len(context) > 0 else '',
                candidate.lower()
            )

            # If candidate improves score, add bonus
            if candidate_score > original_score:
                improvement = min((candidate_score - original_score) / 5.0, 0.3)
                score += improvement

        return min(score, 1.0)


# ============================================================================
# METHOD 6: STRUCTURAL PATTERN VALIDATION
# ============================================================================

class StructuralValidator:
    """Validate structural patterns in parliamentary text"""

    def __init__(self, config: dict):
        self.patterns = {
            name: re.compile(pattern)
            for name, pattern in config['structural_patterns'].items()
        }

    def validate_structure(self, page: dict) -> List[ErrorCandidate]:
        """Validate structural patterns in page"""
        errors = []
        markdown = page.get('markdown', '')
        page_idx = page.get('index', 0)

        # Check for common structural issues
        lines = markdown.split('\n')

        for i, line in enumerate(lines):
            # Check for malformed speaker attributions
            if '.—' in line and not self.patterns['speaker'].match(line):
                # Potential malformed speaker
                # This is complex to auto-correct, so just flag it
                errors.append(ErrorCandidate(
                    page_index=page_idx,
                    original_word=line[:50],
                    position=markdown.find(line),
                    error_types=['structural_malformation'],
                    suggested_corrections=[],
                    context=line
                ))

        return errors


# ============================================================================
# MAIN PIPELINE
# ============================================================================

class OCRCorrector:
    """Main OCR correction pipeline"""

    def __init__(self, config: dict):
        self.config = config
        self.data_dir = Path(config['data_dir'])

        # Bootstrap data
        bootstrapper = DataBootstrapper(config['data_dir'])
        bootstrapper.bootstrap_all()

        # Initialize components (will be set after loading data)
        self.dict_checker = None
        self.confusion_detector = None
        self.entity_validator = None
        self.ngram_scorer = None
        self.edit_corrector = None
        self.struct_validator = None

    def process_file(self, input_path: str, output_report: str, output_corrected: str):
        """Process OCR file and generate corrections"""

        # Load data
        print(f"\n=== Loading {input_path} ===")
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        pages = data.get('pages', [])
        print(f"✓ Loaded {len(pages)} pages\n")

        # Initialize all components
        print("=== Initializing Components ===")
        self.dict_checker = DictionaryChecker(self.config, self.data_dir)
        self.confusion_detector = ConfusionDetector(self.config, self.dict_checker)
        self.entity_validator = EntityValidator(self.config)
        self.ngram_scorer = NgramScorer(pages, self.config)
        self.edit_corrector = EditDistanceCorrector(self.config, self.dict_checker, self.ngram_scorer)
        self.struct_validator = StructuralValidator(self.config)

        # Extract entities (needs full corpus)
        entities = self.entity_validator.extract_entities(pages)
        print()

        # Process pages
        print("=== Processing Pages ===")
        all_errors = []
        corrections_applied = 0

        for i, page in enumerate(pages):
            if i % 100 == 0:
                print(f"Processing page {i}/{len(pages)}...")

            page_errors = self._process_page(page)
            all_errors.extend(page_errors)

            # Auto-apply high-confidence corrections
            page['markdown'], applied = self._apply_corrections(
                page['markdown'],
                page_errors,
                self.config['auto_correct_threshold']
            )
            corrections_applied += applied

        print(f"✓ Processed {len(pages)} pages")
        print(f"✓ Found {len(all_errors)} potential errors")
        print(f"✓ Auto-applied {corrections_applied} high-confidence corrections\n")

        # Write outputs
        print("=== Writing Outputs ===")
        self._write_report(all_errors, output_report)
        self._write_corrected(data, output_corrected)
        self._write_statistics(all_errors, entities)

        print("\n=== Complete ===")
        print(f"Report: {output_report}")
        print(f"Corrected file: {output_corrected}")
        print(f"Statistics: ocr-statistics.json")

    def _process_page(self, page: dict) -> List[ErrorCandidate]:
        """Process a single page through all methods"""
        errors = []
        markdown = page.get('markdown', '')
        page_idx = page.get('index', 0)

        # Tokenize with positions
        words_with_pos = self._tokenize_with_positions(markdown)
        words = [w for w, _ in words_with_pos]

        # METHOD 1: Dictionary check
        for word, pos in words_with_pos:
            if not self.dict_checker.check_word(word):
                error = ErrorCandidate(
                    page_index=page_idx,
                    original_word=word,
                    position=pos,
                    error_types=['unknown_word'],
                    suggested_corrections=[],
                    context=self._get_context(markdown, pos)
                )
                errors.append(error)

        # METHOD 2: Confusion patterns (enrich errors)
        for error in errors:
            confusions = self.confusion_detector.find_confusion_patterns(error.original_word)
            if confusions:
                error.error_types.append('confusion_pattern')
                error.suggested_corrections.extend(confusions)

        # METHOD 3: Entity consistency
        entity_errors = self.entity_validator.find_inconsistencies(page)
        errors.extend(entity_errors)

        # METHOD 4: N-gram scoring
        low_scores = self.ngram_scorer.score_sequence(words)
        for word_idx, word, score in low_scores:
            # Find position in original text
            if word_idx < len(words_with_pos):
                _, pos = words_with_pos[word_idx]
                errors.append(ErrorCandidate(
                    page_index=page_idx,
                    original_word=word,
                    position=pos,
                    error_types=['low_ngram_score'],
                    suggested_corrections=[],
                    context=self._get_context(markdown, pos)
                ))

        # METHOD 5: Edit distance corrections (enrich all errors)
        for error in errors:
            # Get context words
            context_words = self._get_context_words(words, error.original_word)

            # Generate corrections
            edit_corrections = self.edit_corrector.generate_corrections(
                error.original_word,
                context_words
            )

            # Merge with existing suggestions
            error.suggested_corrections = self._merge_suggestions(
                error.suggested_corrections,
                edit_corrections
            )

        # METHOD 6: Structural validation
        struct_errors = self.struct_validator.validate_structure(page)
        errors.extend(struct_errors)

        return errors

    def _tokenize_with_positions(self, text: str) -> List[Tuple[str, int]]:
        """Tokenize text and track positions"""
        words_with_pos = []
        for match in re.finditer(r'\b[A-Za-z]+\b', text):
            words_with_pos.append((match.group(0), match.start()))
        return words_with_pos

    def _get_context(self, text: str, pos: int, window: int = 50) -> str:
        """Get context around position"""
        start = max(0, pos - window)
        end = min(len(text), pos + window)
        return text[start:end]

    def _get_context_words(self, all_words: List[str], target: str, window: int = 3) -> List[str]:
        """Get surrounding words for context"""
        try:
            idx = all_words.index(target)
            start = max(0, idx - window)
            return [w.lower() for w in all_words[start:idx]]
        except ValueError:
            return []

    def _merge_suggestions(self, list1: List[Tuple[str, float]], list2: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """Merge two suggestion lists, keeping highest confidence"""
        suggestions = {}
        for word, conf in list1 + list2:
            if word not in suggestions or conf > suggestions[word]:
                suggestions[word] = conf

        # Sort by confidence
        return sorted(suggestions.items(), key=lambda x: x[1], reverse=True)

    def _apply_corrections(self, text: str, errors: List[ErrorCandidate], threshold: float) -> Tuple[str, int]:
        """Apply high-confidence corrections to text"""
        # Sort errors by position (reverse order to maintain positions)
        errors_sorted = sorted(errors, key=lambda e: e.position, reverse=True)

        applied = 0
        for error in errors_sorted:
            if error.suggested_corrections:
                best_correction, confidence = error.suggested_corrections[0]

                if confidence >= threshold:
                    # Apply correction
                    pos = error.position
                    word_len = len(error.original_word)

                    # Preserve capitalization pattern
                    if error.original_word.isupper():
                        best_correction = best_correction.upper()
                    elif error.original_word[0].isupper():
                        best_correction = best_correction.capitalize()

                    # Replace
                    text = text[:pos] + best_correction + text[pos + word_len:]
                    applied += 1

        return text, applied

    def _write_report(self, errors: List[ErrorCandidate], output_path: str):
        """Write detailed error report"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for error in errors:
                f.write(json.dumps(error.to_dict()) + '\n')
        print(f"✓ Wrote corrections report: {output_path}")

    def _write_corrected(self, data: dict, output_path: str):
        """Write corrected JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Wrote corrected file: {output_path}")

    def _write_statistics(self, errors: List[ErrorCandidate], entities: Dict[str, NamedEntity]):
        """Write statistics summary"""
        stats = {
            'total_errors_found': len(errors),
            'errors_by_type': Counter(),
            'top_errors': Counter(),
            'entity_variants': {}
        }

        for error in errors:
            for error_type in error.error_types:
                stats['errors_by_type'][error_type] += 1

            if error.suggested_corrections:
                best_correction = error.suggested_corrections[0][0]
                stats['top_errors'][(error.original_word, best_correction)] += 1

        # Convert counters to lists
        stats['errors_by_type'] = dict(stats['errors_by_type'])
        stats['top_errors'] = [
            {
                'original': orig,
                'suggested': sugg,
                'count': count
            }
            for (orig, sugg), count in stats['top_errors'].most_common(20)
        ]

        # Entity variants
        for entity in entities.values():
            if len(entity.variants) > 1:
                stats['entity_variants'][entity.canonical] = list(entity.variants)

        with open('ocr-statistics.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        print(f"✓ Wrote statistics: ocr-statistics.json")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='OCR Error Detection and Correction for Parliamentary Texts'
    )
    parser.add_argument(
        '--input',
        default='mirror-ocr-11-2-ALL-pages-parsed.json',
        help='Input JSON file (default: mirror-ocr-11-2-ALL-pages-parsed.json)'
    )
    parser.add_argument(
        '--output-report',
        default='ocr-corrections-report.jsonl',
        help='Output report file (default: ocr-corrections-report.jsonl)'
    )
    parser.add_argument(
        '--output-corrected',
        default='mirror-ocr-11-2-ALL-pages-corrected.json',
        help='Output corrected file (default: mirror-ocr-11-2-ALL-pages-corrected.json)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.90,
        help='Auto-correction confidence threshold (default: 0.90)'
    )
    parser.add_argument(
        '--data-dir',
        default='data',
        help='Data directory for dictionaries (default: data/)'
    )

    args = parser.parse_args()

    # Update config with args
    CONFIG['auto_correct_threshold'] = args.threshold
    CONFIG['data_dir'] = args.data_dir

    # Run correction
    corrector = OCRCorrector(CONFIG)
    corrector.process_file(args.input, args.output_report, args.output_corrected)


if __name__ == '__main__':
    main()
