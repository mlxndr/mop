import json
import re
import difflib
from pathlib import Path

# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------

INPUT_JSON = "mirror-ocr-11-2-ALL-pages-corrected-enchant.json"   # combined page-level OCR JSON
OUTPUT_JSONL = "11-2-speeches-corr.jsonl"           # one speech per line
SOURCE_DOC_ID = "11-2"                         # your identifier for this volume

# --------------------------------------------------------------------
# Helpers: paragraph splitting
# --------------------------------------------------------------------


def split_markdown_into_paragraphs(md: str):
    """
    Split markdown text into paragraphs: groups of non-empty lines
    separated by one or more blank lines.
    """
    paragraphs = []
    buf = []

    for line in md.splitlines():
        if line.strip() == "":
            if buf:
                paragraphs.append("\n".join(buf).strip())
                buf = []
        else:
            buf.append(line)
    if buf:
        paragraphs.append("\n".join(buf).strip())

    return paragraphs


# --------------------------------------------------------------------
# Helpers: house & Latin date detection
# --------------------------------------------------------------------

HOUSE_HEADING_RE = re.compile(r"^\s*HOUSE OF (COMMONS|LORDS)\.?\s*$",
                              re.IGNORECASE)

# Canonical Latin month forms (roughly) and their month numbers.
# We'll fuzzy-match OCR’d tokens to these.
LATIN_MONTHS = {
    "JANUARII": 1,
    "FEBRUARII": 2,
    "MARTII": 3,
    "APRILIS": 4,
    "MAII": 5,
    "JUNII": 6,
    "JULII": 7,
    "AUGUSTI": 8,
    "SEPTEMBRIS": 9,
    "OCTOBRIS": 10,
    "NOVEMBRIS": 11,
    "DECEMBRIS": 12,
}


def detect_simple_house(paragraph: str):
    """
    Detect a bare 'HOUSE OF COMMONS.' or 'HOUSE OF LORDS.' line.
    Returns normalised house name or None.
    """
    m = HOUSE_HEADING_RE.match(paragraph.strip())
    if m:
        which = m.group(1).upper()
        return f"HOUSE OF {which}"
    return None


def parse_latin_date_line(text: str):
    """
    Parse lines like:
      'HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834.'
    into '1834-02-04'.

    Returns ISO date string or None.
    """
    up = re.sub(r"[.,;:—\-]+", " ", text.upper())
    tokens = [t for t in up.split() if t]

    # Only treat as a Latin date if DIE is a separate token and there is at least one digit
    if "DIE" not in tokens or not any(ch.isdigit() for ch in up):
        return None

    # Extract numeric tokens (day + year)
    num_tokens = [t for t in tokens if re.search(r"\d", t)]
    nums = []
    for t in num_tokens:
        digits = re.sub(r"\D", "", t)
        if digits:
            nums.append(int(digits))

    if len(nums) < 2:
        return None

    day = nums[0]
    year = nums[-1]

    # Month token: prefer the word after DIE, else the last non-numeric before the year
    month_token = None

    if "DIE" in tokens:
        idx = tokens.index("DIE")
        if idx + 1 < len(tokens):
            month_token = re.sub(r"[^A-Z]", "", tokens[idx + 1])

    if not month_token:
        year_idx = max(i for i, t in enumerate(tokens) if re.search(r"\d", t))
        for j in range(year_idx - 1, -1, -1):
            if re.search(r"[A-Z]", tokens[j]) and not re.search(r"\d", tokens[j]):
                month_token = re.sub(r"[^A-Z]", "", tokens[j])
                break

    if not month_token:
        return None

    canonical_keys = list(LATIN_MONTHS.keys())
    match = difflib.get_close_matches(month_token, canonical_keys, n=1, cutoff=0.5)
    if not match:
        return None

    month = LATIN_MONTHS[match[0]]
    return f"{year:04d}-{month:02d}-{day:02d}"


def detect_latin_house_and_date(paragraph: str):
    """
    Detect combined house+Latin date lines, e.g.
      'HOUSE OF LORDS, MARTIS, 4° DIE FEBRUARII, 1834.'

    Returns (house, date_raw, date_iso), or (None, None, None) if not such a line.
    """
    text = paragraph.strip()
    if not text:
        return None, None, None

    up = text.upper()

    # HARD GUARD 1: genuine headings start with 'HOUSE OF ...'
    # Do NOT treat '... printed by the House of Lords, that ...'
    # as a heading.
    if not up.startswith("HOUSE OF "):
        return None, None, None

    # Determine which House
    if up.startswith("HOUSE OF LORDS"):
        house = "HOUSE OF LORDS"
    elif up.startswith("HOUSE OF COMMONS"):
        house = "HOUSE OF COMMONS"
    else:
        return None, None, None

    # Clean punctuation and tokenise
    up_clean = re.sub(r"[.,;:—\-]+", " ", up)
    tokens = [t for t in up_clean.split() if t]

    # HARD GUARD 2: requires DIE token and at least one digit
    if "DIE" not in tokens or not any(ch.isdigit() for ch in up):
        return None, None, None

    # Try to actually parse a date
    date_iso = parse_latin_date_line(text)
    if not date_iso:
        # If we can't parse a plausible Latin date, this isn't a heading
        return None, None, None

    date_raw = text
    return house, date_raw, date_iso

# --------------------------------------------------------------------
# Helpers: debate title detection (ALL CAPS lines)
# --------------------------------------------------------------------


def is_all_caps_heading(paragraph: str):
    """
    Debate titles are typically ALL CAPS lines (possibly with punctuation),
    e.g. 'NOTICES OF MOTIONS.' or 'CORN LAWS.'
    """
    text = paragraph.strip()

    # Ignore obviously non-headings
    if len(text) == 0:
        return False
    if "\n" in text:
        return False  # multi-line paragraphs are more likely speech text

    # Remove non-letters and see if what's left is all caps
    letters = re.sub(r"[^A-Za-z]+", "", text)
    if not letters:
        return False

    if not letters.isupper():
        return False

    # Avoid capturing the bare HOUSE headings as debate titles
    if text.upper().startswith("HOUSE OF "):
        return False

    return True


# --------------------------------------------------------------------
# Helpers: speaker detection & splitting
# --------------------------------------------------------------------

# Core pattern for a speaker heading at the start of a line:
# e.g. "Mr. H. HANDLEY.—", "The CHANCELLOR of the EXCHEQUER.—",
#      "The DUKE of SUTHERLAND.—", "LORD HOWARD OF EFFINGHAM.—",
#      "Several Irish Members together.—", "An HONOURABLE MEMBER.—"
SPEAKER_HEADING_CORE = r"""
    # Commons / titled individuals
    (?:Mr|MR|H.|Mrs|MRS|Miss|MISS|Sir|SIR|Dr|DR)\.?\s+[A-Z][^\n—]*? |
    (?:LORD|Lord|EARL|Earl|VISCOUNT|Viscount|DUKE|Duke|MARQUESS|Marquess)\s+[A-Z][^\n—]*? |
    The\s+[A-Z][A-Za-z]+[^\n—]*? |
    # Collective / generic interjectors:
    # "Several Irish Members together", "Several Honourable Members",
    # "Many Honourable Members", "An HONOURABLE MEMBER"
    (?:Several|SEVERAL|Many|MANY|An|AN|A|a)\s+
        [A-Z][A-Za-z]+
        (?:\s+[A-Z][A-Za-z]+)*      # optional extra capitalised words, e.g. "Irish", "Honourable"
        \s+Members?                 # Member / Members
        (?:\s+together)?            # optional "together"
        \.?                         # optional trailing dot
"""

SPEAKER_HEADING_RE = re.compile(
    rf"""^
        (?P<speaker>{SPEAKER_HEADING_CORE})
        \s*—
    """,
    re.VERBOSE,
)

SPEAKER_HEADING_RE_MULTILINE = re.compile(
    rf"""(?m)       # multiline mode
        ^
        (?P<speaker>{SPEAKER_HEADING_CORE})
        \s*—
    """,
    re.VERBOSE,
)

# Fallback for short items without a dash:
# e.g. "Mr. SPRING RICE presented a Bill...", "Mr. PINNEY presented a petition..."
SIMPLE_NAME_AT_START_RE = re.compile(
    r"""^
        (?P<name>
            (?:Mr|MR|Mrs|MRS|H|Miss|MISS|Sir|SIR|Lord|LORD|
             Colonel|COLONEL|Major|MAJOR|Captain|CAPTAIN)\.?
            \s+
            [A-Z][A-Za-z\.'-]+
            (?:\s+[A-Z][A-Za-z\.'-]+)*   # allow multi-word surnames: "SPRING RICE"
        )
        \b
    """,
    re.VERBOSE,
)


def normalise_speaker_label(raw: str) -> str:
    speaker = raw.strip()
    # Strip trailing punctuation clusters and re-add a single full stop
    speaker = re.sub(r"[,\.;:]+$", "", speaker).strip()
    if not speaker.endswith("."):
        speaker = speaker + "."
    return speaker

# --------------------------------------------------------------------
# Speaker heading patterns
# --------------------------------------------------------------------

# Things that can appear as the "label" of a speaker, *without* the dash
# e.g. "Mr. SPRING RICE", "The DUKE of GORDON", "An HONOURABLE MEMBER", etc.
SPEAKER_LABEL_CORE_RE = re.compile(
    r"""^(
        # Ordinary titled names: Mr. SPRING RICE, Sir ROBERT PEEL, Dr. LUSHINGTON
        (?:
            (?:Mr|MR|Mrs|MRS|Ms|MISS|Sir|SIR|Dr|DR|
             Lord|LORD|Earl|EARL|Viscount|VISCOUNT|
             Marquess|MARQUESS|Duke|DUKE|
             Colonel|COLONEL|Captain|CAPTAIN|Major|MAJOR)
            \.?
            (?:\s+[A-Z][A-Za-z\.'-]+)*
        )
        |
        # Office-holders with "The": The LORD CHANCELLOR, The DUKE of GORDON, etc.
        (?:
            The\s+
            (?:
                (?:Lord|LORD|Earl|EARL|Viscount|VISCOUNT|
                 Marquess|MARQUESS|Duke|DUKE|
                 Bishop|BISHOP|Archbishop|ARCHBISHOP|
                 Chancellor|CHANCELLOR|Speaker|SPEAKER)
                (?:\s+of\s+[A-Z][A-Za-z\.'-]+)*
            )
        )
        |
        # Collective attributions we *do* want as speakers:
        (?:An|AN|A|SEVERAL|Several)\s+
        (?:HONOURABLE|Honourable)\s+
        Members?
        (?:\s+together)?
    )$""",
    re.VERBOSE,
)

def looks_like_speaker_label(label: str) -> bool:
    s = label.strip().rstrip(" .")
    if len(s) < 3 or len(s) > 80:
        return False
    return SPEAKER_LABEL_CORE_RE.match(s) is not None


# Heading with dash: "The DUKE of SUTHERLAND.—My Lords, ..."
SPEAKER_HEADING_RE = re.compile(
    r"""^
        (?P<label>
            # Re-use the "core" patterns but without anchoring
            (?:
                (?:Mr|MR|Mrs|MRS|Ms|MISS|Sir|SIR|Dr|DR|
                 Lord|LORD|Earl|EARL|Viscount|VISCOUNT|
                 Marquess|MARQUESS|Duke|DUKE|
                 Colonel|COLONEL|Captain|CAPTAIN|Major|MAJOR)
                \.?
                (?:\s+[A-Z][A-Za-z\.'-]+)*
            )
            |
            (?:
                The\s+
                (?:
                    (?:Lord|LORD|Earl|EARL|Viscount|VISCOUNT|
                     Marquess|MARQUESS|Duke|DUKE|
                     Bishop|BISHOP|Archbishop|ARCHBISHOP|
                     Chancellor|CHANCELLOR|Speaker|SPEAKER)
                    (?:\s+of\s+[A-Z][A-Za-z\.'-]+)*
                )
            )
            |
            # "An Honourable Member", "Several Honourable Members", etc.
            (?:
                (?:An|AN|A|SEVERAL|Several)\s+
                (?:HONOURABLE|Honourable)\s+
                Members?
                (?:\s+together)?
            )
        )
        \s*[—\-]\s*
    """,
    re.VERBOSE,
)

# Label + verb patterns without dash, e.g.
# "Mr. SPRING RICE presented a Bill ..."
# "The DUKE of GORDON presented petitions ..."
SPEAKER_LABEL_WITH_VERB_COMMA_RE = re.compile(
    r"""^
        (?P<label>[^,]+?)
        ,\s+
        (?:
            on\s+presenting|
            on\s+moving|
            on\s+bringing|
            on\s+introducing
        )
        \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

SPEAKER_LABEL_WITH_VERB_RE = re.compile(
    r"""^
        (?P<label>.+?)
        \s+
        (?:
            presented|
            presents|
            brought\s+up|
            brought\s+in|
            gave\s+notice|
            then\s+gave\s+notice|
            gives\s+notice|
            moved|
            moves|
            rose\s+to\s+move|
            rose\s+to\s+call|
            called\s+the\s+attention|
            called\s+attention|
            put\s+the\s+question|
            stated
        )
        \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# --------------------------------------------------------------------
# Speaker heuristics: generic non-speaker prefixes
# --------------------------------------------------------------------

GENERIC_NON_SPEAKERS_PREFIXES = (
    "THE NOBLE DUKE",
    "THE NOBLE LORD",
    "THE NOBLE MARQUESS",
    "THE HONOURABLE MEMBER",
    "THE HONOURABLE GENTLEMAN",
    "THE HONOURABLE BARONET",
    "THE RIGHT HONOURABLE GENTLEMAN",
    "THE RIGHT HONOURABLE BARONET",
    "THE SIREXISTS STATED",
    "THE BILL BEFORE THE HOUSE",
)

def is_generic_non_speaker(label: str) -> bool:
    """
    Filter out phrases we know are NOT intended as speaker labels,
    even if they superficially look like them.
    """
    up = label.upper().strip().rstrip(".:;—-")
    return any(up.startswith(p) for p in GENERIC_NON_SPEAKERS_PREFIXES)

def detect_speaker(paragraph: str):
    """
    Try to extract a speaker name / label from the start of a paragraph.
    Returns a string (speaker) or None.
    """
    text = paragraph.strip()
    first_line = text.split("\n", 1)[0].strip()

    # 1) Patterns like "Mr. O'CONNELL.—", "An HONOURABLE MEMBER.—", etc.
    dash_pattern = re.compile(
        r"^("                                     # start of label
        r"(?:Mr|MR|Mrs|MRS|Miss|MISS|Ms|MS|Dr|DR"
        r"|Sir|SIR|Lord|LORD|Lady|LADY"
        r"|Colonel|COLONEL|Major|MAJOR|Captain|CAPTAIN"
        r"|Viscount|VISCOUNT|Earl|EARL|Duke|DUKE|Marquess|MARQUESS"
        r"|The\s+LORD\s+CHANCELLOR"
        r"|The\s+CHANCELLOR\s+of\s+the\s+EXCHEQUER"
        r"|The\s+ATTORNEY\s+GENERAL"
        r"|The\s+SOLICITOR\s+GENERAL"
        r"|An?\s+HONOURABLE\s+MEMBER(?:\s+for\s+[A-Z][A-Za-z'\-]+)?"
        r"|Several\s+Honourable\s+Members"
        r"|Several\s+Irish\s+Members\s+together"
        r"|Many\s+Honourable\s+Members"
        r"|[A-Z][A-Z\s\.'-]+)"
        r")\s*[–—\-]\s"                           # dash after label
    )
    m = dash_pattern.match(first_line)
    if m:
        label = m.group(1).strip().rstrip(".,;:—-")
        if not is_generic_non_speaker(label):
            return label

    # 2) Patterns like "Mr. O'CONNELL moved ...", "Dr. LUSHINGTON presented ..."
    notif_pattern = re.compile(
        r"^("                                     # label
        r"(?:Mr|MR|Mrs|MRS|Miss|MISS|Ms|MS|Dr|DR"
        r"|Sir|SIR|Lord|LORD|Lady|LADY"
        r"|Colonel|COLONEL|Major|MAJOR|Captain|CAPTAIN"
        r"|Viscount|VISCOUNT|Earl|EARL|Duke|DUKE|Marquess|MARQUESS"
        r"|The\s+MARQUESS\s+of\s+[A-Z][A-Za-z'-]+"
        r"|The\s+EARL\s+of\s+[A-Z][A-Za-z'-]+"
        r"|The\s+DUKE\s+of\s+[A-Z][A-Za-z'-]+"
        r"|The\s+LORD\s+CHANCELLOR"
        r"|The\s+CHANCELLOR\s+of\s+the\s+EXCHEQUER"
        r")(?:\s+[A-Z][A-Za-z\.'-]+)*"            # optional extra surname(s)
        r")\s+"
        r"(presented|brought\s+up|brought\s+in|gave\s+notice"
        r"|then\s+gave\s+notice|moved|rose\s+to\s+move)\b",
        re.IGNORECASE,
    )
    m = notif_pattern.match(first_line)
    if m:
        label = m.group(1).strip().rstrip(".,;:—-")
        if not is_generic_non_speaker(label):
            return label

    # 3) Simple "Mr. NAME ..." / "Dr. NAME ..." without dash or verb pattern
    simple_name_pattern = re.compile(
        r"^((?:Mr|MR|Mrs|MRS|Miss|MISS|Ms|MS|Dr|DR"
        r"|Sir|SIR|Lord|LORD|Lady|LADY"
        r"|Colonel|COLONEL|Major|MAJOR|Captain|CAPTAIN)\.?\s+[A-Z][A-Za-z\.'-]+)"
    )
    m = simple_name_pattern.match(first_line)
    if m:
        label = m.group(1).strip().rstrip(".,;:—-")
        if not is_generic_non_speaker(label):
            return label

    # IMPORTANT: no "ALLCAPS prefix" fallback here; it caused too many false positives.
    return None

def split_paragraph_into_speeches(paragraph: str):
    """
    If a single paragraph contains multiple speaker headings, split it
    into (speaker, text) chunks.

    Returns a list of (speaker, text) tuples, or an empty list if
    no speaker headings are found.
    """
    text = paragraph.strip()
    matches = list(SPEAKER_HEADING_RE_MULTILINE.finditer(text))
    if not matches:
        return []

    chunks = []
    for i, m in enumerate(matches):
        speaker_raw = m.group("speaker")
        speaker = normalise_speaker_label(speaker_raw)

        start = m.end()  # after the dash
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            chunks.append((speaker, content))

    return chunks

# --------------------------------------------------------------------
# Main conversion logic
# --------------------------------------------------------------------


def load_pages(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "pages" in data:
        pages = data["pages"]
    elif isinstance(data, list):
        pages = data
    else:
        raise ValueError("Unrecognised JSON structure: expected dict with 'pages' or a list")

    return pages


def speeches_from_pages(pages):
    """
    Turn page-level OCR pages into a list of speech dicts.

    Each speech dict contains:
      - house
      - date_raw (Latin line, as seen)
      - date_iso (parsed ISO date or None)
      - debate_title
      - speaker
      - pages (set of page indices)
      - text
    """
    speeches = []

    current_house = None
    current_date_raw = None
    current_date_iso = None
    current_debate = None

    current_speech = None  # dict with metadata + text + pages(set)

    def start_new_speech(speaker, page_index):
        nonlocal current_speech
        # flush the previous speech, if any
        if current_speech and current_speech["text"].strip():
            speeches.append(current_speech)
        current_speech = {
            "house": current_house,
            "date_raw": current_date_raw,
            "date_iso": current_date_iso,
            "debate_title": current_debate,
            "speaker": speaker,
            "pages": set([page_index]),
            "text": "",
        }

    def append_to_current_speech(text_fragment, page_index):
        nonlocal current_speech
        if current_speech is None:
            # Narrative / rubric with no assigned speaker: ignore for now
            return
        frag = text_fragment.strip()
        if not frag:
            return
        if current_speech["text"]:
            current_speech["text"] += "\n\n" + frag
        else:
            current_speech["text"] = frag
        current_speech["pages"].add(page_index)

    # Iterate pages in index order (use global_index if present)
    pages_sorted = sorted(
        pages,
        key=lambda p: p.get("global_index", p.get("index", 0)),
    )

    for page in pages_sorted:
        page_index = page.get("global_index", page.get("index"))
        md = page.get("markdown", "")

        paragraphs = split_markdown_into_paragraphs(md)

        for para in paragraphs:
            p = para.strip()
            if not p:
                continue

            # 1) Combined house + Latin date line
            house2, date_raw2, date_iso2 = detect_latin_house_and_date(p)
            if house2 or date_raw2 or date_iso2:
                if current_speech and current_speech["text"].strip():
                    speeches.append(current_speech)
                current_speech = None

                if house2:
                    current_house = house2
                if date_raw2 or date_iso2:
                    current_date_raw = date_raw2
                    current_date_iso = date_iso2

                # This is purely metadata, not speech content
                continue

            # 2) Simple 'HOUSE OF COMMONS.' / 'HOUSE OF LORDS.' line
            house = detect_simple_house(p)
            if house:
                if current_speech and current_speech["text"].strip():
                    speeches.append(current_speech)
                current_speech = None
                current_house = house
                continue

            # 3) Debate title in ALL CAPS
            if is_all_caps_heading(p):
                current_debate = p
                # Don't force-close speech here; a speech may begin immediately after
                continue

            # 4) Multi-speaker paragraphs (e.g. Q + A in one block)
            chunks = split_paragraph_into_speeches(p)
            if chunks:
                for speaker, content in chunks:
                    start_new_speech(speaker, page_index)
                    append_to_current_speech(content, page_index)
                continue  # paragraph fully handled

            # 5) Single-speaker paragraph (heading at the start)
            speaker = detect_speaker(p)

            # Extra paranoia: if somehow we got something very long and weird,
            # discard it as a speaker.
            if speaker and len(speaker) > 80:
                speaker = None

            if speaker:
                start_new_speech(speaker, page_index)
                # Strip the heading + dash from the paragraph before appending
                # so we don't duplicate the label in the text.
                # We can reuse the regex here.
                m = SPEAKER_HEADING_RE.match(p)
                if m:
                    content = p[m.end():].strip()
                else:
                    content = p
                append_to_current_speech(content, page_index)
            else:
                # 6) Continuation paragraph for the current speaker
                append_to_current_speech(p, page_index)

    # Flush final speech
    if current_speech and current_speech["text"].strip():
        speeches.append(current_speech)

    return speeches


def write_speeches_jsonl(speeches, path: Path):
    with path.open("w", encoding="utf-8") as f:
        for i, sp in enumerate(speeches, start=1):
            record = {
                "id": f"{SOURCE_DOC_ID}_speech_{i:06d}",
                "house": sp["house"],
                "date_iso": sp["date_iso"],
                "debate_title": sp["debate_title"],
                "speaker": sp["speaker"],
                "pages": sorted(sp["pages"]),
                "text": sp["text"],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    in_path = Path(INPUT_JSON)
    out_path = Path(OUTPUT_JSONL)

    print(f"Loading pages from {in_path} …")
    pages = load_pages(in_path)
    print(f"Loaded {len(pages)} pages")

    print("Extracting speeches …")
    speeches = speeches_from_pages(pages)
    print(f"Extracted {len(speeches)} candidate speeches")

    print(f"Writing JSONL to {out_path} …")
    write_speeches_jsonl(speeches, out_path)

    print("Done.")


if __name__ == "__main__":
    main()