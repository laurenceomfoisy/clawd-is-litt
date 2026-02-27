# 📚 Clawd is Lit - Autonomous Literature Research Pipeline

**Autonomous scholarly literature research pipeline built by Ti-Clawd** 

From research question to full Zotero library with PDFs in one command.

## 🚀 Features

- **Autonomous Discovery**: Search Google Scholar automatically
- **Multi-Source PDF Fetching**: Tries legal sources first (Unpaywall), falls back to Sci-Hub
- **Zotero Integration**: Adds papers with full metadata + PDFs automatically
- **Robust Error Handling**: Logs what worked/failed for each paper
- **Mirror Rotation**: Tries multiple Sci-Hub mirrors when one fails
- **Progress Tracking**: Real-time progress bars and detailed logging

## 📋 Requirements

- Python 3.8+
- [zotero-cli](https://github.com/e-bug/zotero-cli) (for Zotero integration)
- Zotero account with API key

## 🔧 Installation

1. **Clone the repository:**
```bash
git clone https://github.com/laurenceomfoisy/clawd-is-lit.git
cd clawd-is-lit
```

2. **Create virtual environment and install dependencies:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure Zotero credentials:**

Create `~/.openclaw/workspace/.zotero-config.json`:
```json
{
  "api_key": "YOUR_ZOTERO_API_KEY",
  "user_id": "YOUR_ZOTERO_USER_ID"
}
```

Get your API key from: https://www.zotero.org/settings/keys

4. **Install zotero-cli:**
```bash
pip install zotero-cli
```

5. **Customize config (optional):**

Edit `config.yaml` to change Sci-Hub mirrors, email, PDF download directory, etc.

## 📖 Usage

### Basic Search
```bash
source venv/bin/activate
python research.py "your research question" --max-papers 10
```

### Add to Specific Collection
```bash
python research.py "machine learning transformers" --max-papers 20 --collection "ML Research"
```

### Custom Config
```bash
python research.py "climate change" --max-papers 15 --config custom-config.yaml
```

## 🏗️ Architecture

```
research.py           # Main CLI entry point
├── scholar_search.py # Google Scholar discovery
├── pdf_fetcher.py    # Multi-source PDF acquisition
│   ├── Unpaywall API (legal open access)
│   └── Sci-Hub mirrors (fallback)
└── zotero_manager.py # Zotero API integration
```

## 🔍 How It Works

1. **Search Google Scholar** for your research question
2. **Extract metadata** (title, authors, year, DOI, citations)
3. **Fetch PDFs** from multiple sources:
   - First: Unpaywall API (legal open access)
   - Fallback: Sci-Hub mirrors (rotates through working mirrors)
4. **Add to Zotero** with full metadata + PDF attachments
5. **Report summary** (papers found, PDFs fetched, items added)

## 📊 Example Output

```
Searching Google Scholar for query: political polarization social media
Processing papers: 100%|██████████| 10/10 [00:45<00:00,  4.5s/paper]
Summary: 10 papers found, 7 PDFs fetched, 10 added to Zotero
```

## ⚙️ Configuration (config.yaml)

```yaml
scihub_mirrors:
  - sci-hub.se
  - sci-hub.st
  - sci-hub.ru
  - sci-hub.mksa.top
unpaywall_email: your-email@example.com
zotero_config_path: ~/.openclaw/workspace/.zotero-config.json
pdf_download_dir: ~/literature-pdfs/
```

## 🛠️ Components

### scholar_search.py
- Scrapes Google Scholar results
- Extracts: title, authors, year, DOI, URL, snippet, citations
- Handles rate limiting gracefully

### pdf_fetcher.py
- **Unpaywall API**: Checks for legal open access versions
- **Sci-Hub**: Rotates through mirrors for paywalled papers
- Validates DOIs, handles network errors, logs all attempts

### zotero_manager.py
- Creates journal articles in Zotero
- Attaches PDFs as child items
- Uses zotero-cli subprocess calls

## 📝 Logging

All operations are logged to `literature.log`:
```
2026-02-27 15:58:41 [INFO] Searching Google Scholar for query: ...
2026-02-27 15:58:44 [INFO] Fetched PDF via Sci-Hub for DOI ...
2026-02-27 15:58:52 [INFO] Created Zotero item with key SUFPB5VB
```

## 🚨 Limitations

- **Google Scholar rate limiting**: May block IP after many requests (use VPN/proxies)
- **DOI availability**: Not all papers have DOIs exposed by Scholar
- **Sci-Hub mirrors**: Domains change frequently (update config.yaml)
- **Legal considerations**: Sci-Hub access varies by jurisdiction

## 🤝 Contributing

Built by **Ti-Clawd** using OpenCode (openai/gpt-5.3-codex).

Improvements welcome:
- Better DOI extraction from Scholar
- Additional PDF sources (arXiv, ResearchGate, PubMed Central)
- Collection management features
- Duplicate detection

## 📜 License

MIT License - Use responsibly and respect copyright laws in your jurisdiction.

## 🙏 Acknowledgments

- [zotero-cli](https://github.com/e-bug/zotero-cli) for Zotero API integration
- [Unpaywall](https://unpaywall.org/) for open access discovery
- Google Scholar for academic search

## ⚠️ Disclaimer

This tool is for **research and educational purposes**. Users are responsible for complying with applicable laws and regulations regarding access to copyrighted materials. The authors do not condone copyright infringement.

---

**Built with 🐾 by Ti-Clawd**
