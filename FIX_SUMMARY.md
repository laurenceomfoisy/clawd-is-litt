# Literature Pipeline Fixes - 2026-02-27

## Issues Fixed

### 1. Scholar Scraping - Author Parsing ✅
**Problem**: Google Scholar uses non-breaking spaces (`\xa0`) before the " - " separator, causing author parsing to fail.
**Example bad data**: `"2026"`, `"Misinformation and…"`, `"International Relations"` were being captured as authors.

**Fix**: Updated `scholar_search.py` → `_extract_authors()` to handle both regular spaces and non-breaking spaces:
```python
segment = re.split(r'[\xa0\s]-', authors_blob, maxsplit=1)[0]
```

**Result**: Now correctly extracts only author names before the first separator.

### 2. Zotero Metadata - Author Format ✅
**Problem**: `add_paper_to_group()` was using single `name` field for all authors instead of `firstName`/`lastName` split.
**Fix**: Switched to use the existing `_author_creators()` helper function that properly formats names.

**Result**: Authors now appear correctly in Zotero with proper first/last name fields.

### 3. Zotero API - REST Instead of CLI ✅
**Problem**: Using `zotero-cli` subprocess was brittle and hard to debug.
**Fix**: Switched to direct REST API calls using `requests` library.

**Benefits**:
- Better error handling
- Clearer logging
- Proper PDF upload support
- No shell injection risks

### 4. Metadata Repair Script ✅
**Added**: `fix_existing_metadata.py` to repair existing Zotero items with bad metadata.

**Features**:
- Detects bad author data (numbers, truncated text, separators)
- Re-scrapes Scholar for correct metadata
- Updates Zotero items via REST API
- Progress logging with success/skip/fail counts

## Results

### Existing 60 Papers in Zotero Collection
- ✅ **Fixed**: 5 papers (successfully re-scraped and updated)
- ✅ **Already OK**: 34 papers (had valid authors already)
- ⚠️ **Failed**: 21 papers (Scholar couldn't find them)

**Papers fixed:**
1. "Artificial Intelligence and Big Data in Global Politics" - now shows "F Carrillo" (was "2026", "Misinformation…")
2. "How Will AI Steal Our Elections?" - now shows "Yu"
3. "Artificial intelligence: Risks to privacy and democracy" - now shows "Manheim, Kaplan"
4. "Foreign electoral interference" - now shows "Mohan, Wall"
5. "[C] Regulating Digital Platforms" - now shows "Ziaei"

**Papers that failed** (21 total):
- Mostly papers with [CITATION] [C] prefixes (unpublished/preprints)
- Very niche/recent papers not indexed by Scholar
- Papers with truncated or non-standard titles

**Recommendation**: Manually edit the 21 failed papers in Zotero if author info is critical, or accept as-is (they still have titles, DOIs, etc.).

## PDF Attachment Status

### Current: 3/60 PDFs fetched (5%)
**Why so low?**
- Most DOIs fail with 422 errors from Unpaywall (encoding issues, not in database)
- Sci-Hub mirrors mostly blocked/down:
  - sci-hub.se: DNS failure
  - sci-hub.st: 403 Forbidden
  - sci-hub.ru: Works but limited coverage
  - sci-hub.mksa.top: 403 Forbidden

**Recommendation for Laurence**: Access PDFs via ULaval institutional access:
1. Open Zotero web library
2. Click paper DOI link
3. Use "Obtenir @ULaval" button
4. Or connect via ULaval VPN for automatic access

## Repository Updates

**Pushed to GitHub**: https://github.com/laurenceomfoisy/clawd-is-litt
- Commit: 169219a
- All fixes included
- Updated README with metadata quality notes

## Future Improvements

### For PDF Fetching
1. Add arXiv detection and direct PDF download
2. Try direct PDF extraction from Scholar result URLs
3. Add more working Sci-Hub mirrors as they become available
4. Implement institutional access integration (if ULaval provides API)

### For Metadata
1. Add publication title scraping from Scholar
2. Better handling of [CITATION] placeholder titles
3. Implement fuzzy title matching for failed Scholar lookups

## Usage

### For new searches (metadata now fixed):
```bash
cd ~/.openclaw/workspace/literature
source venv/bin/activate
python research.py "your research question" --max-papers 20
```

### To repair existing broken Zotero items:
```bash
cd ~/.openclaw/workspace/literature
source venv/bin/activate
python fix_existing_metadata.py
```

## Summary

**Metadata quality**: ✅ FIXED - Future searches will have clean author data
**Existing data**: ⚠️ PARTIALLY FIXED - 5 papers repaired, 21 couldn't be auto-fixed
**PDF fetching**: ⚠️ STILL LOW (~5%) - Recommend using ULaval institutional access
**Tool reliability**: ✅ IMPROVED - Better error handling, logging, and API usage
