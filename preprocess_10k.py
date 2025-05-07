import os
import re
import argparse
import time
from typing import Optional, List, Dict
from collections import Counter

# Attempt to import LangChain PDF loader, else fallback to PyPDF2
try:
    from langchain_community.document_loaders import PyPDFLoader
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    from PyPDF2 import PdfReader

import nltk

# Download NLTK resources if not already present
for resource in ['tokenizers/punkt', 'corpora/stopwords']:
    try:
        nltk.data.find(resource)
    except LookupError:
        nltk.download(resource.split('/')[-1])

# Common financial/legal boilerplate patterns
BOILERPLATE_PATTERNS = [
    r"Form\s+10-K",
    r"Annual\s+Report\s+pursuant\s+to\s+Section",
    r"For\s+the\s+fiscal\s+year\s+ended",
    r"Commission\s+file\s+number",
    r"Securities\s+registered\s+pursuant\s+to\s+Section",
    r"Indicate\s+by\s+check\s+mark",
    r"incorporated\s+by\s+reference",
    r"DOCUMENTS\s+INCORPORATED\s+BY\s+REFERENCE",
    r"TABLE\s+OF\s+CONTENTS",
    r"^\s*Page\s*$",
    r"^\s*\d+\s*$",
    r"^\s*PART\s+[IV]+\s*$",
    r"^\s*ITEM\s+\d+[A-Z]?\s*$",
]

# Precompile regexes for performance
device_boilerplate_regexes = [re.compile(pat, re.IGNORECASE) for pat in BOILERPLATE_PATTERNS]
ITEM_REGEX = re.compile(r"(?:ITEM|Item)\s+(\d+[A-Z]?)[.\s]+([^\n]+)")


def extract_full_text(pdf_path: str) -> List[Dict]:
    """Extract text from PDF with page numbers."""
    if HAS_LANGCHAIN:
        loader = PyPDFLoader(pdf_path)
        pages_loaded = loader.load()
        return [
            {'page_num': i+1, 'content': page.page_content}
            for i, page in enumerate(pages_loaded)
        ]
    else:
        reader = PdfReader(pdf_path)
        return [
            {'page_num': i+1, 'content': page.extract_text() or ''}
            for i, page in enumerate(reader.pages)
        ]


def clean_headers_footers(pages: List[Dict]) -> List[Dict]:
    """Remove repeating headers and footers efficiently."""
    total = len(pages)
    sample = min(5, total)
    all_lines = []
    for page in pages[:sample]:
        for ln in page['content'].split('\n'):
            ln = ln.strip()
            if ln and len(ln) < 100:
                all_lines.append(ln)
    threshold = max(2, total * 0.05)
    repeater = Counter(all_lines)
    repeating = {ln for ln, cnt in repeater.items() if cnt >= threshold}

    cleaned = []
    for page in pages:
        kept = [ln for ln in page['content'].split('\n') if ln.strip() not in repeating]
        cleaned.append({'page_num': page['page_num'], 'content': '\n'.join(kept)})
    return cleaned


def remove_boilerplate(text: str) -> str:
    """Strip boilerplate patterns."""
    for rx in device_boilerplate_regexes:
        text = rx.sub('', text)
    text = re.sub(r"\d+\s*U\.S\.C\.|§\s*\d+[a-z]*", '', text)
    text = re.sub(r"\s{2,}", ' ', text)
    text = re.sub(r"\n{2,}", '\n', text)
    return text.strip()


def clean_section(text: str) -> str:
    """Normalize section text."""
    text = re.sub(r"[•◦●▪]", '* ', text)
    text = re.sub(r"\r\n?", '\n', text)
    text = re.sub(r"\t", ' ', text)
    text = re.sub(r"\s{2,}", ' ', text)
    text = re.sub(r"\n{3,}", '\n\n', text)
    return text.strip()


def extract_sections(pages: List[Dict]) -> Dict[str, str]:
    """Extract key sections from 10-K based on Item numbers."""
    full = '\n'.join(page['content'] for page in pages)
    matches = list(ITEM_REGEX.finditer(full))
    sections = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i+1].start() if i < len(matches)-1 else len(full)
        sec = clean_section(full[start:end])
        sec = remove_boilerplate(sec)
        if len(sec) > 100:
            sections[f"Item {m.group(1)}: {m.group(2).strip()}"] = sec
    if matches:
        meta = clean_section(full[:matches[0].start()])
        if meta:
            sections['Company Information'] = meta
    return sections


def preprocess_10k(input_pdf: str, output_txt: Optional[str] = None) -> str:
    """Preprocess pipeline: extract, clean, section."""
    print("Extracting text from PDF...", flush=True)
    t0 = time.time()
    pages = extract_full_text(input_pdf)
    print(f"Extraction took {time.time()-t0:.1f}s for {len(pages)} pages", flush=True)

    print("Cleaning headers and footers...", flush=True)
    t1 = time.time()
    cleaned = clean_headers_footers(pages)
    print(f"Cleaning took {time.time()-t1:.1f}s", flush=True)

    print("Extracting key sections...", flush=True)
    t2 = time.time()
    sections = extract_sections(cleaned)
    print(f"Section extraction took {time.time()-t2:.1f}s for {len(sections)} sections", flush=True)

    final = ''.join(f"\n\n== {k} ==\n\n{v}" for k,v in sections.items())
    final = re.sub(r"\s{2,}", ' ', final)
    final = re.sub(r"\n{3,}", '\n\n', final)

    out = output_txt or os.path.splitext(input_pdf)[0] + '_processed.txt'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(final.strip())
    print(f"Processed text saved to: {out}", flush=True)
    return out


def main():
    parser = argparse.ArgumentParser(description='Preprocess 10-K PDF')
    parser.add_argument('--file', '-f', required=True, help='Path to 10-K PDF')
    parser.add_argument('--out', '-o', help='Output path for processed text')
    args = parser.parse_args()
    preprocess_10k(args.file, args.out)

if __name__ == '__main__':
    main()