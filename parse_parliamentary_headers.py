#!/usr/bin/env python3
"""
Parse UK Parliamentary OCR text to extract headers and remove footers.

This script processes OCR'd UK Parliamentary text from 1834, extracting
page headers into separate JSON fields and removing page footers.
"""

import json
import re
from typing import Dict, List, Tuple, Optional


def is_speaker_line(line: str) -> bool:
    """
    Check if a line is a speaker (actual person speaking).

    Examples of speakers:
    - "The EARL of ROSEBERY.—"
    - "Mr. O'CONNELL.—"
    - "LORD HOWARD OF EFFINGHAM.—"
    """
    # Check for speaker patterns (name followed by .— or similar)
    # This matches patterns like "The DUKE of X.—" or "Mr. NAME.—"
    if re.search(r'^(The |Mr\. |Sir |Colonel |Major |Lord |Lady |Earl |Duke |Captain |Baron )', line, re.IGNORECASE):
        if '.—' in line or '—' in line:
            return True

    return False


def extract_header(markdown: str) -> Tuple[Optional[List[str]], str]:
    """
    Extract header lines from the beginning of markdown text.

    Headers are lines like:
    - "HOUSE OF COMMONS."
    - "HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834."
    - "HOUSE OF COMMONS.\n\nPRIVATE BUSINESS.\n\nST. PANCRAS PAVING BILL."

    Returns:
        Tuple of (header_lines, remaining_markdown)
    """
    lines = markdown.split('\n')
    header_lines = []

    # Check if the first non-empty line is a parliamentary header
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

    # Check if it starts with HOUSE OF COMMONS or HOUSE OF LORDS
    if not (first_line.startswith('HOUSE OF COMMONS') or
            first_line.startswith('HOUSE OF LORDS')):
        return None, markdown

    # This is a header - extract it and subsequent header lines
    header_lines.append(first_line)
    current_idx = first_line_idx + 1

    # Continue extracting header lines
    # Header sections can include additional lines like "PRIVATE BUSINESS.", "APPEALS.", etc.
    # We'll look ahead to see if there are more ALL CAPS section titles
    max_lookahead = 10  # Look ahead up to 10 lines for more header content

    while current_idx < len(lines):
        line = lines[current_idx].strip()

        # Empty lines - skip but continue looking
        if not line:
            current_idx += 1
            continue

        # Check if this is a speaker (actual person speaking - end of header)
        if is_speaker_line(line):
            break

        # Check if line contains a date pattern (part of header)
        if re.search(r'\d+[°*]\s*DIE\s+\w+,?\s*\d{4}', line):
            header_lines.append(line)
            current_idx += 1
            continue

        # Check if line is all caps (likely a header/section title)
        if line.isupper():
            # All caps lines are headers unless they're very long paragraphs
            if len(line) < 150:
                header_lines.append(line)
                current_idx += 1
                continue
            else:
                # Very long all-caps line - likely content, not header
                break

        # Not all caps - this could be actual content
        # But let's look ahead to see if there are more ALL CAPS header lines coming
        # (in case there's a mixed-case OCR error)
        found_more_header = False
        for lookahead in range(1, min(max_lookahead, len(lines) - current_idx)):
            future_line = lines[current_idx + lookahead].strip()
            if future_line and future_line.isupper() and len(future_line) < 100:
                # Found another header line ahead - keep going
                found_more_header = True
                break
            elif future_line and not future_line.isupper() and not is_speaker_line(future_line):
                # Found actual content - stop looking ahead
                break

        if not found_more_header:
            # No more headers found - we're done
            break

        current_idx += 1

    # Skip any trailing empty lines before content starts
    while current_idx < len(lines) and not lines[current_idx].strip():
        current_idx += 1

    # Join remaining lines as the markdown content
    remaining_markdown = '\n'.join(lines[current_idx:])

    return header_lines if header_lines else None, remaining_markdown


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


def process_page(page: Dict) -> Dict:
    """
    Process a single page, extracting headers and removing footers.

    Args:
        page: Dictionary containing page data with 'markdown' field

    Returns:
        Updated page dictionary with 'header' field and cleaned 'markdown'
    """
    markdown = page.get('markdown', '')

    # Extract header
    header_lines, remaining_markdown = extract_header(markdown)

    # Remove footer
    cleaned_markdown = remove_footer(remaining_markdown)

    # Create updated page
    updated_page = page.copy()

    if header_lines:
        updated_page['header'] = header_lines

    updated_page['markdown'] = cleaned_markdown

    return updated_page


def process_json_file(input_path: str, output_path: str):
    """
    Process the entire JSON file, extracting headers and removing footers.

    Args:
        input_path: Path to input JSON file
        output_path: Path to output JSON file
    """
    # Read input file
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Process each page
    if 'pages' in data:
        data['pages'] = [process_page(page) for page in data['pages']]

    # Write output file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Processed {len(data.get('pages', []))} pages")
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
