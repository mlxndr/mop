#!/usr/bin/env python3
"""
Parse UK Parliamentary OCR text to extract headers and remove footers.

This script processes OCR'd UK Parliamentary text from 1834, extracting
HOUSE OF LORDS/COMMONS page headers (only) into separate JSON fields,
removing page footers, and joining hyphenated words across page boundaries.
"""

import json
import re
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher


def fuzzy_match(text: str, target: str, threshold: float = 0.8) -> bool:
    """
    Check if text fuzzy matches target (for OCR errors).

    Args:
        text: Text to check
        target: Target string to match against
        threshold: Similarity threshold (0-1)

    Returns:
        True if similarity >= threshold
    """
    similarity = SequenceMatcher(None, text.upper(), target.upper()).ratio()
    return similarity >= threshold


def is_date_header(line: str) -> bool:
    """
    Check if a line is a standalone date header.

    Examples:
    - "FEBRUARY 4"
    - "February 5, 18"
    - "MARCH 10, 1834."

    Pattern: Month name followed by numbers, punctuation, and optionally I/i/l
    """
    line_stripped = line.strip()

    # Month names (various cases due to OCR)
    months = ['january', 'february', 'march', 'april', 'may', 'june',
              'july', 'august', 'september', 'october', 'november', 'december',
              'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

    # Check if starts with a month name
    first_word = line_stripped.split()[0] if line_stripped.split() else ''
    if first_word.lower() not in months:
        return False

    # Get the rest after the month
    rest = line_stripped[len(first_word):].strip()

    # Should contain only numbers, punctuation, and I/i/l
    # Allow common date punctuation and roman numerals
    allowed_chars = set('0123456789.,;:°*\' -—IilVXLCDM')

    if not rest:
        return False

    # Check if all remaining characters are allowed
    for char in rest:
        if char not in allowed_chars:
            return False

    return True


def is_parliamentary_house_header(line: str) -> bool:
    """
    Check if a line is a HOUSE OF LORDS or HOUSE OF COMMONS header.
    Uses fuzzy matching to handle OCR errors.

    Examples:
    - "HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834."
    - "HOUSE OF COMMONS."
    - "HOUSE OF COMMONS, 110 181001" (OCR error)
    """
    line_upper = line.upper().strip()

    # Check for fuzzy match with HOUSE OF LORDS or HOUSE OF COMMONS
    if (fuzzy_match(line_upper[:15] if len(line_upper) >= 15 else line_upper, "HOUSE OF LORDS", 0.75) or
        fuzzy_match(line_upper[:17] if len(line_upper) >= 17 else line_upper, "HOUSE OF COMMONS", 0.75)):
        return True

    return False


def is_header_line(line: str) -> bool:
    """
    Check if a line is any type of header (HOUSE or DATE).
    """
    return is_parliamentary_house_header(line) or is_date_header(line)


def extract_header(markdown: str) -> Tuple[Optional[str], str]:
    """
    Extract header lines from the beginning.

    Extracts headers like:
    - "HOUSE OF COMMONS."
    - "HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834."
    - "FEBRUARY 4"
    - "February 5, 18"

    Does NOT extract section titles like "PRIVATE BUSINESS", "SELECT VESTRIES BILL"
    as these need to stay with the speeches.

    Returns:
        Tuple of (header_line, remaining_markdown)
    """
    lines = markdown.split('\n')

    # Check if the first non-empty line is a header
    first_line_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped:
            first_line_idx = i
            break
    else:
        # All lines are empty
        return None, markdown

    first_line = lines[first_line_idx].strip()

    # Check if it's a header (HOUSE or DATE)
    if not is_header_line(first_line):
        return None, markdown

    # Extract only this header line
    # Check if followed by two line breaks (empty line)
    has_double_break = False
    if first_line_idx + 1 < len(lines) and not lines[first_line_idx + 1].strip():
        has_double_break = True

    # Only extract if it has the double line break pattern
    if not has_double_break:
        return None, markdown

    # Skip the header line and the following empty line(s)
    current_idx = first_line_idx + 1
    while current_idx < len(lines) and not lines[current_idx].strip():
        current_idx += 1

    # Join remaining lines as the markdown content
    remaining_markdown = '\n'.join(lines[current_idx:])

    return first_line, remaining_markdown


def remove_footer(markdown: str) -> str:
    """
    Remove footer patterns from the end of markdown text.

    Footers match patterns like:
    - "No. XL.—Sess. 1834."
    - "No. XL.—Sept. 1834."
    - "No. I.—Sess. 1834."
    - "No. XII.—Sezs. 1834."
    """
    # Pattern to match footers at the end
    # Matches: \n\nNo. [Roman/Arabic numerals].—[Sess|Sept|Sezs]. 1834.\n\n
    # Allow for OCR variations in spelling
    footer_pattern = r'\n\s*No\.\s+[IVXLCDM\d]+\.?—[A-Za-z]+\.\s*1834\.\s*\n*\s*$'

    # Remove the footer if found
    cleaned = re.sub(footer_pattern, '', markdown, flags=re.IGNORECASE)

    # Also clean up any trailing whitespace
    cleaned = cleaned.rstrip()

    return cleaned


def join_hyphenated_words(prev_markdown: str, curr_markdown: str) -> Tuple[str, str]:
    """
    Join hyphenated words that span across two pages.

    If the previous page ends with a hyphenated word (e.g., "some-"),
    and the current page starts with the continuation (e.g., "thing"),
    join them together.

    Does NOT join if the current page starts with a header that will be extracted.

    Args:
        prev_markdown: Markdown from previous page
        curr_markdown: Markdown from current page

    Returns:
        Tuple of (updated_prev_markdown, updated_curr_markdown)
    """
    if not prev_markdown or not curr_markdown:
        return prev_markdown, curr_markdown

    # Check if previous page ends with a hyphen followed by optional whitespace
    prev_match = re.search(r'(\S+)-\s*$', prev_markdown)
    if not prev_match:
        return prev_markdown, curr_markdown

    # Strip leading whitespace from current page to find what comes next
    curr_stripped = curr_markdown.lstrip()

    # Check if current page starts with a header (which will be extracted)
    # In this case, don't join - the header will be removed separately
    first_line = curr_stripped.split('\n')[0] if curr_stripped else ''
    if is_header_line(first_line):
        return prev_markdown, curr_markdown

    # Check if current page starts with a word (orphan)
    # The orphan should be lowercase to be a continuation
    curr_match = re.match(r'^([a-z]+)', curr_stripped)
    if not curr_match:
        return prev_markdown, curr_markdown

    orphan_part = curr_match.group(1)

    # Orphan must be lowercase (true word continuation, not a new sentence)
    if not orphan_part.islower():
        return prev_markdown, curr_markdown

    # Orphan should typically be short (a real fragment, not a full word)
    # Allow up to 15 chars to handle legitimate long word fragments
    if len(orphan_part) > 15:
        return prev_markdown, curr_markdown

    # Get the hyphenated part
    hyphen_part = prev_match.group(1)

    # Join them: remove the hyphen from prev and add the orphan
    joined_word = hyphen_part + orphan_part

    # Calculate how much leading whitespace to preserve
    leading_space = curr_markdown[:len(curr_markdown) - len(curr_stripped)]

    # Update previous page: replace "word-" at end with joined word
    updated_prev = prev_markdown[:prev_match.start()] + joined_word

    # Update current page: remove the orphan, keep rest
    orphan_end = curr_match.end()
    # Remove the orphan from the stripped version
    remaining = curr_stripped[orphan_end:]

    # Restore leading space if the next char isn't whitespace already
    if remaining and not remaining[0].isspace():
        updated_curr = leading_space + remaining
    else:
        updated_curr = remaining.lstrip()

    return updated_prev, updated_curr


def process_page(page: Dict) -> Dict:
    """
    Process a single page, extracting headers and removing footers.

    Args:
        page: Dictionary containing page data with 'markdown' field

    Returns:
        Updated page dictionary with 'header' field and cleaned 'markdown'
    """
    markdown = page.get('markdown', '')

    # Extract header (only HOUSE OF LORDS/COMMONS)
    header_line, remaining_markdown = extract_header(markdown)

    # Remove footer
    cleaned_markdown = remove_footer(remaining_markdown)

    # Create updated page
    updated_page = page.copy()

    if header_line:
        updated_page['header'] = header_line

    updated_page['markdown'] = cleaned_markdown

    return updated_page


def process_json_file(input_path: str, output_path: str):
    """
    Process the entire JSON file, extracting headers, removing footers,
    and joining hyphenated words across pages.

    Args:
        input_path: Path to input JSON file
        output_path: Path to output JSON file
    """
    # Read input file
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'pages' not in data:
        print("No pages found in JSON")
        return

    # First pass: Process each page (extract headers, remove footers)
    processed_pages = [process_page(page) for page in data['pages']]

    # Second pass: Join hyphenated words across page boundaries
    for i in range(len(processed_pages) - 1):
        prev_page = processed_pages[i]
        curr_page = processed_pages[i + 1]

        prev_markdown = prev_page.get('markdown', '')
        curr_markdown = curr_page.get('markdown', '')

        # Join hyphenated words
        updated_prev, updated_curr = join_hyphenated_words(prev_markdown, curr_markdown)

        # Update the pages if changes were made
        if updated_prev != prev_markdown:
            processed_pages[i]['markdown'] = updated_prev
            processed_pages[i + 1]['markdown'] = updated_curr

    data['pages'] = processed_pages

    # Count statistics
    headers_extracted = sum(1 for p in processed_pages if 'header' in p)

    # Write output file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Processed {len(processed_pages)} pages")
    print(f"Headers extracted: {headers_extracted}")
    print(f"Output written to: {output_path}")


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) < 2:
        input_file = 'mirror-ocr-11-2-ALL-pages.json'
        output_file = 'mirror-ocr-11-2-ALL-pages-parsed.json'
    elif len(sys.argv) < 3:
        input_file = sys.argv[1]
        output_file = input_file.replace('.json', '-parsed.json')
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2]

    print(f"Processing: {input_file}")
    print(f"Output to: {output_file}")

    process_json_file(input_file, output_file)


if __name__ == '__main__':
    main()
