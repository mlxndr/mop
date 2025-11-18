#!/usr/bin/env python3
"""
Convert spell-checked 1834 UK Parliamentary OCR data into annotated linguistic corpus.

Outputs multiple formats:
1. CoNLL-U (Universal Dependencies standard)
2. TEI XML (Text Encoding Initiative for digital humanities)
3. Vertical format (CQPweb/Sketch Engine compatible)
4. JSON with linguistic annotations

Uses spaCy for:
- Part-of-speech tagging
- Lemmatization
- Named Entity Recognition
- Dependency parsing
- Sentence segmentation
"""

import json
import spacy
import re
from typing import List, Dict, TextIO
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom


class ParliamentaryCorpusAnnotator:
    def __init__(self, spacy_model: str = "en_core_web_lg"):
        """
        Initialize the annotator with a spaCy model.

        Args:
            spacy_model: spaCy model name (en_core_web_sm/md/lg/trf)
        """
        print(f"Loading spaCy model: {spacy_model}")
        print("(This may take a minute on first run...)")

        try:
            self.nlp = spacy.load(spacy_model)
        except OSError:
            print(f"\n❌ Model '{spacy_model}' not found!")
            print(f"Installing it now with: python -m spacy download {spacy_model}")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", spacy_model])
            self.nlp = spacy.load(spacy_model)

        print(f"✓ Loaded spaCy model: {spacy_model}")

        # Add custom rules for parliamentary entities
        self._add_parliamentary_patterns()

        self.stats = {
            'speeches_processed': 0,
            'tokens_annotated': 0,
            'sentences_segmented': 0,
            'entities_found': 0
        }

    def _add_parliamentary_patterns(self):
        """Add custom entity recognition patterns for parliamentary texts."""
        # Add ruler for parliamentary titles
        if "entity_ruler" not in self.nlp.pipe_names:
            ruler = self.nlp.add_pipe("entity_ruler", before="ner")

            patterns = [
                # Titles
                {"label": "TITLE", "pattern": [{"LOWER": "lord"}, {"IS_TITLE": True}]},
                {"label": "TITLE", "pattern": [{"LOWER": "earl"}, {"TEXT": "of"}, {"IS_TITLE": True}]},
                {"label": "TITLE", "pattern": [{"LOWER": "duke"}, {"TEXT": "of"}, {"IS_TITLE": True}]},
                {"label": "TITLE", "pattern": [{"LOWER": "sir"}, {"IS_TITLE": True}]},
                {"label": "TITLE", "pattern": [{"TEXT": "Mr."}, {"IS_TITLE": True}]},

                # Houses
                {"label": "ORG", "pattern": "HOUSE OF LORDS"},
                {"label": "ORG", "pattern": "HOUSE OF COMMONS"},
                {"label": "ORG", "pattern": "Parliament"},
            ]

            ruler.add_patterns(patterns)

    def annotate_speech(self, speech: Dict) -> Dict:
        """
        Annotate a single speech with linguistic information.

        Args:
            speech: Dictionary with speech metadata and text

        Returns:
            Dictionary with original metadata + linguistic annotations
        """
        text = speech.get('text', '')

        # Process with spaCy
        doc = self.nlp(text)

        # Extract annotations
        sentences = []
        for sent in doc.sents:
            tokens = []
            for token in sent:
                tokens.append({
                    'id': token.i - sent.start + 1,  # Sentence-relative ID
                    'form': token.text,
                    'lemma': token.lemma_,
                    'upos': token.pos_,  # Universal POS
                    'xpos': token.tag_,  # Penn Treebank POS
                    'feats': str(token.morph) if token.morph else '_',
                    'head': token.head.i - sent.start + 1 if token.head.i != token.i else 0,
                    'deprel': token.dep_,
                    'start_char': token.idx,
                    'end_char': token.idx + len(token.text),
                    'whitespace': token.whitespace_
                })

            sentences.append({
                'text': sent.text,
                'tokens': tokens
            })

        # Extract named entities
        entities = []
        for ent in doc.ents:
            entities.append({
                'text': ent.text,
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char
            })

        # Update stats
        self.stats['speeches_processed'] += 1
        self.stats['tokens_annotated'] += len(doc)
        self.stats['sentences_segmented'] += len(list(doc.sents))
        self.stats['entities_found'] += len(doc.ents)

        return {
            **speech,  # Preserve original metadata
            'sentences': sentences,
            'entities': entities,
            'token_count': len(doc),
            'sentence_count': len(sentences)
        }

    def to_conllu(self, annotated_speech: Dict, file_handle: TextIO):
        """
        Write annotated speech to CoNLL-U format.

        CoNLL-U format:
        # sent_id = speech_id-sent_num
        # text = sentence text
        ID  FORM  LEMMA  UPOS  XPOS  FEATS  HEAD  DEPREL  DEPS  MISC
        """
        speech_id = annotated_speech['id']

        for sent_num, sentence in enumerate(annotated_speech['sentences'], 1):
            # Metadata comments
            file_handle.write(f"# sent_id = {speech_id}-{sent_num}\n")
            file_handle.write(f"# text = {sentence['text']}\n")
            file_handle.write(f"# speaker = {annotated_speech.get('speaker', 'Unknown')}\n")
            file_handle.write(f"# house = {annotated_speech.get('house', 'Unknown')}\n")
            file_handle.write(f"# date = {annotated_speech.get('date_iso', 'Unknown')}\n")

            # Tokens
            for token in sentence['tokens']:
                line = '\t'.join([
                    str(token['id']),
                    token['form'],
                    token['lemma'],
                    token['upos'],
                    token['xpos'],
                    token['feats'],
                    str(token['head']),
                    token['deprel'],
                    '_',  # DEPS (not used)
                    '_'   # MISC (not used)
                ])
                file_handle.write(line + '\n')

            # Blank line between sentences
            file_handle.write('\n')

    def to_vertical(self, annotated_speech: Dict, file_handle: TextIO):
        """
        Write annotated speech to vertical format (CQPweb/Sketch Engine).

        Format: one token per line
        <speech id="..." speaker="..." house="..." date="...">
        <s>
        word\tlemma\tpos
        ...
        </s>
        </speech>
        """
        speech_id = annotated_speech['id']
        speaker = annotated_speech.get('speaker', 'Unknown')
        house = annotated_speech.get('house', 'Unknown')
        date = annotated_speech.get('date_iso', 'Unknown')

        # Speech header
        file_handle.write(f'<speech id="{speech_id}" speaker="{speaker}" house="{house}" date="{date}">\n')

        for sentence in annotated_speech['sentences']:
            file_handle.write('<s>\n')

            for token in sentence['tokens']:
                line = '\t'.join([
                    token['form'],
                    token['lemma'],
                    token['upos'],
                    token['xpos']
                ])
                file_handle.write(line + '\n')

            file_handle.write('</s>\n')

        file_handle.write('</speech>\n')

    def to_tei_xml(self, annotated_speeches: List[Dict], output_file: str):
        """
        Write annotated speeches to TEI XML format.

        TEI (Text Encoding Initiative) is the standard for digital humanities.
        """
        # Create TEI root
        TEI = ET.Element('TEI', xmlns="http://www.tei-c.org/ns/1.0")

        # TEI Header
        teiHeader = ET.SubElement(TEI, 'teiHeader')
        fileDesc = ET.SubElement(teiHeader, 'fileDesc')

        titleStmt = ET.SubElement(fileDesc, 'titleStmt')
        ET.SubElement(titleStmt, 'title').text = "British Parliamentary Debates, 1834 (Volume 11-2)"
        ET.SubElement(titleStmt, 'respStmt').text = "Digitized and annotated corpus"

        publicationStmt = ET.SubElement(fileDesc, 'publicationStmt')
        ET.SubElement(publicationStmt, 'p').text = f"Created: {datetime.now().isoformat()}"

        sourceDesc = ET.SubElement(fileDesc, 'sourceDesc')
        ET.SubElement(sourceDesc, 'p').text = "OCR-scanned and spell-checked parliamentary proceedings from 1834"

        # Encoding description
        encodingDesc = ET.SubElement(teiHeader, 'encodingDesc')
        ET.SubElement(encodingDesc, 'p').text = "Annotated with spaCy for POS, lemmas, NER, and dependencies"

        # Text body
        text = ET.SubElement(TEI, 'text')
        body = ET.SubElement(text, 'body')

        # Group speeches by date/debate
        for speech in annotated_speeches:
            div = ET.SubElement(body, 'div', type="speech")
            div.set('xml:id', speech['id'])
            div.set('who', speech.get('speaker', 'Unknown'))
            div.set('when', speech.get('date_iso', 'Unknown'))

            # Add metadata
            head = ET.SubElement(div, 'head')
            head.text = speech.get('debate_title', '')

            # Add annotated sentences
            for sentence in speech['sentences']:
                s = ET.SubElement(div, 's')

                for token in sentence['tokens']:
                    w = ET.SubElement(s, 'w')
                    w.text = token['form']
                    w.set('lemma', token['lemma'])
                    w.set('pos', token['upos'])
                    w.set('msd', token['xpos'])  # morphosyntactic description

                # Add trailing whitespace/punctuation handling
                if sentence['tokens']:
                    last_token = sentence['tokens'][-1]
                    if last_token['whitespace']:
                        s.tail = last_token['whitespace']

        # Pretty print and save
        xml_str = minidom.parseString(ET.tostring(TEI)).toprettyxml(indent="  ")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        print(f"✓ Saved TEI XML: {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert spell-checked parliamentary OCR to annotated corpus"
    )
    parser.add_argument(
        '--input',
        default='mirror-ocr-11-2-ALL-pages-corrected-enchant.json',
        help='Input JSON file (spell-checked OCR pages)'
    )
    parser.add_argument(
        '--speeches',
        default='11-2-speeches.jsonl',
        help='Input JSONL file with speeches'
    )
    parser.add_argument(
        '--output-dir',
        default='corpus_output',
        help='Output directory for corpus files'
    )
    parser.add_argument(
        '--format',
        choices=['conllu', 'vertical', 'tei', 'json', 'all'],
        default='all',
        help='Output format (default: all)'
    )
    parser.add_argument(
        '--spacy-model',
        default='en_core_web_lg',
        help='spaCy model to use (sm/md/lg/trf)'
    )
    parser.add_argument(
        '--sample',
        type=int,
        help='Process only first N speeches (for testing)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("PARLIAMENTARY CORPUS ANNOTATOR")
    print("=" * 70)
    print(f"Input speeches: {args.speeches}")
    print(f"Output dir: {args.output_dir}")
    print(f"Format: {args.format}")
    print("=" * 70)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Initialize annotator
    annotator = ParliamentaryCorpusAnnotator(spacy_model=args.spacy_model)

    # Load speeches
    print(f"\nLoading speeches from {args.speeches}...")
    speeches = []
    with open(args.speeches, 'r', encoding='utf-8') as f:
        for line in f:
            speeches.append(json.loads(line))

    if args.sample:
        speeches = speeches[:args.sample]
        print(f"✓ Loaded {len(speeches)} speeches (SAMPLE MODE)")
    else:
        print(f"✓ Loaded {len(speeches)} speeches")

    # Annotate speeches
    print(f"\nAnnotating speeches with linguistic features...")
    annotated_speeches = []

    for i, speech in enumerate(speeches):
        if i % 100 == 0:
            print(f"  Processing speech {i+1}/{len(speeches)}...")

        annotated = annotator.annotate_speech(speech)
        annotated_speeches.append(annotated)

    print(f"\n✓ Annotated {len(annotated_speeches)} speeches")
    print(f"  Tokens: {annotator.stats['tokens_annotated']:,}")
    print(f"  Sentences: {annotator.stats['sentences_segmented']:,}")
    print(f"  Entities: {annotator.stats['entities_found']:,}")

    # Output in requested formats
    print(f"\nGenerating corpus files...")

    if args.format in ['conllu', 'all']:
        conllu_file = output_dir / 'parliamentary-1834.conllu'
        with open(conllu_file, 'w', encoding='utf-8') as f:
            for speech in annotated_speeches:
                annotator.to_conllu(speech, f)
        print(f"✓ CoNLL-U: {conllu_file}")

    if args.format in ['vertical', 'all']:
        vert_file = output_dir / 'parliamentary-1834.vert'
        with open(vert_file, 'w', encoding='utf-8') as f:
            for speech in annotated_speeches:
                annotator.to_vertical(speech, f)
        print(f"✓ Vertical: {vert_file}")

    if args.format in ['tei', 'all']:
        tei_file = output_dir / 'parliamentary-1834.xml'
        annotator.to_tei_xml(annotated_speeches, str(tei_file))

    if args.format in ['json', 'all']:
        json_file = output_dir / 'parliamentary-1834-annotated.jsonl'
        with open(json_file, 'w', encoding='utf-8') as f:
            for speech in annotated_speeches:
                f.write(json.dumps(speech, ensure_ascii=False) + '\n')
        print(f"✓ JSON: {json_file}")

    # Print summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Speeches processed:   {annotator.stats['speeches_processed']:,}")
    print(f"Tokens annotated:     {annotator.stats['tokens_annotated']:,}")
    print(f"Sentences segmented:  {annotator.stats['sentences_segmented']:,}")
    print(f"Entities found:       {annotator.stats['entities_found']:,}")
    print("=" * 70)
    print("\n✓ Corpus creation complete!")
    print(f"\nOutput files in: {output_dir}/")


if __name__ == '__main__':
    main()
