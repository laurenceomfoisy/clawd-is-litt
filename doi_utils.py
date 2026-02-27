"""
DOI validation and cleaning utilities for the literature research pipeline.
Handles malformed DOIs from Google Scholar and other sources.
"""
import re
from typing import Optional

# Official DOI regex pattern
# Format: 10.{registrant}/{suffix}
# Registrant: 4-9 digits
# Suffix: any character except whitespace
DOI_PATTERN = re.compile(
    r'^10\.\d{4,9}/[^\s]+$',
    re.IGNORECASE
)

# Common DOI prefixes to detect DOIs in text
DOI_PREFIX_PATTERN = re.compile(
    r'10\.\d{4,9}/[^\s]+',
    re.IGNORECASE
)


def extract_doi(text: str) -> Optional[str]:
    """
    Extract a DOI from text (URL, Scholar snippet, etc.).
    
    Examples:
        >>> extract_doi("https://doi.org/10.1234/example")
        '10.1234/example'
        >>> extract_doi("DOI: 10.1234/example")
        '10.1234/example'
    """
    if not text:
        return None
    
    # Find first DOI-like pattern
    match = DOI_PREFIX_PATTERN.search(text)
    if not match:
        return None
    
    return clean_doi(match.group(0))


def clean_doi(doi: str) -> Optional[str]:
    """
    Clean and normalize a DOI string.
    
    Removes common issues:
    - URL prefixes (https://doi.org/, dx.doi.org/, etc.)
    - URL query parameters (&type=pdf, ?download=true, etc.)
    - Trailing punctuation and whitespace
    - HTML entities
    - URL fragments like /1307371 at the end
    
    Examples:
        >>> clean_doi("https://doi.org/10.1234/example")
        '10.1234/example'
        >>> clean_doi("10.1234/example&type=pdf")
        '10.1234/example'
        >>> clean_doi("10.1108/REPS-12-2024-0104/1307371")
        '10.1108/REPS-12-2024-0104'
    """
    if not doi:
        return None
    
    doi = doi.strip()
    
    # Remove common URL prefixes
    prefixes = [
        'https://doi.org/',
        'http://doi.org/',
        'https://dx.doi.org/',
        'http://dx.doi.org/',
        'doi:',
        'DOI:',
    ]
    for prefix in prefixes:
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
            break
    
    # Remove URL query parameters (&..., ?...)
    doi = re.split(r'[&?]', doi)[0]
    
    # Remove HTML entities
    doi = doi.replace('&amp;', '&')
    
    # Remove trailing punctuation
    doi = doi.rstrip('.,;:)')
    
    # Special case: Remove trailing numeric URL fragments ONLY if clearly invalid
    # Example: 10.1108/REPS-12-2024-0104/1307371 (short numeric fragment)
    # But KEEP: 10.1177/2041905820911746 (valid numeric DOI suffix)
    # 
    # Heuristic: Remove ONLY if:
    # - All digits
    # - Short (6-8 chars) - likely a URL path fragment
    # - OR matches known bad patterns
    parts = doi.rsplit('/', 1)
    if len(parts) == 2 and parts[1].isdigit():
        suffix_len = len(parts[1])
        # Remove only SHORT numeric fragments (6-8 chars), not long valid DOI suffixes
        if 6 <= suffix_len <= 8:
            doi = parts[0]
    
    return doi if doi else None


def is_valid_doi(doi: str) -> bool:
    """
    Check if a string is a valid DOI according to official format.
    
    Format: 10.{registrant}/{suffix}
    - Registrant: 4-9 digits
    - Suffix: any non-whitespace characters
    
    Examples:
        >>> is_valid_doi("10.1234/example")
        True
        >>> is_valid_doi("10.1177/2041905820911746")
        True
        >>> is_valid_doi("not-a-doi")
        False
    """
    if not doi:
        return False
    
    return bool(DOI_PATTERN.match(doi.strip()))


def normalize_doi(doi: str) -> Optional[str]:
    """
    Full normalization: extract → clean → validate.
    Returns normalized DOI or None if invalid.
    
    Examples:
        >>> normalize_doi("https://doi.org/10.1234/example&type=pdf")
        '10.1234/example'
        >>> normalize_doi("invalid")
        None
    """
    # Try to extract if it's embedded in text
    extracted = extract_doi(doi) if not doi.strip().startswith('10.') else doi
    
    # Clean it
    cleaned = clean_doi(extracted or doi)
    
    if not cleaned:
        return None
    
    # Validate
    if not is_valid_doi(cleaned):
        return None
    
    return cleaned


# Test suite
if __name__ == "__main__":
    test_cases = [
        # (input, expected_output)
        ("10.1234/example", "10.1234/example"),
        ("https://doi.org/10.1234/example", "10.1234/example"),
        ("10.1234/example&type=pdf", "10.1234/example"),
        ("10.1108/REPS-12-2024-0104/1307371", "10.1108/REPS-12-2024-0104"),
        ("10.1177/2041905820911746", "10.1177/2041905820911746"),
        ("10.1201/9781003594185-8&type=chapterpdf", "10.1201/9781003594185-8"),
        ("10.4324/9781032646930-13/world2vec-vec2politics", "10.4324/9781032646930-13/world2vec-vec2politics"),
        ("not-a-doi", None),
        ("", None),
        ("10.1080/23738871.2020.1797136", "10.1080/23738871.2020.1797136"),
    ]
    
    print("Testing DOI normalization:\n")
    for input_doi, expected in test_cases:
        result = normalize_doi(input_doi)
        status = "✅" if result == expected else "❌"
        print(f"{status} normalize_doi('{input_doi}')")
        print(f"   Expected: {expected}")
        print(f"   Got:      {result}")
        if result != expected:
            print(f"   FAILED!")
        print()
