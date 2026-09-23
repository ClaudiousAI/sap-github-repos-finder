# SAP GitHub Repos Finder

A curated, interactive web app for discovering the top 25 SAP-related GitHub repositories — with rich metadata, filters, and weekly automated updates.

🔗 **Live Demo**: [https://sap-github-repos.streamlit.app](https://sap-github-repos.streamlit.app) *(deploy after setup)*

---

## Features

- **Top 25 SAP Repos** — Ranked by stars, filtered for relevance across 10 SAP areas
- **Rich Metadata** — Primary SAP area, extracted skills, artifact type, purpose, evidence
- **Interactive Filters** — Filter by SAP area (multiselect), search by skill/keyword
- **Detail Drill-down** — Expand any repo for README snippet, topics, matched evidence, GitHub link
- **Export** — Download filtered results as CSV or JSON
- **Weekly Auto-refresh** — GitHub Action runs every Monday, commits updated data
- **Zero-latency UI** — Reads static JSON, no API calls on page load
- **Free Hosting** — Deploys to Streamlit Cloud at no cost

---

## Architecture

```
┌─────────────────────┐     Weekly (Mon 6 AM UTC)     ┌──────────────────┐
│  GitHub Action      │ ─────────────────────────────▶ │  fetch_sap_repos │
│  (.github/workflows)│  1. Checkout (PAT)             │  .py             │
│                     │  2. Setup Python + deps        │                  │
│                     │  3. Run fetch script           │  • 14 queries    │
│                     │  4. Commit sap_top25.json      │  • README parse  │
└─────────────────────┘     (triggers redeploy)        │  • Area classify │
                              │                         │  • Skill extract │
                              ▼                         │  • Rank top 25   │
                       ┌──────────────────┐              └────────┬─────────┘
                       │  Streamlit Cloud │                       │
                       │  (auto-deploy)   │                       ▼
                       └────────┬─────────┘              ┌──────────────────┐
                                │                        │  sap_top25.json  │
                                ▼                        │  (static file)   │
                       ┌──────────────────┐              └────────┬─────────┘
                       │  streamlit_app   │                       │
                       │  .py             │                       ▼
                       │                  │              ┌──────────────────┐
                       │  @st.cache_data  │────────────▶ │  Browser UI      │
                       │  Filters, table  │  reads JSON  │  (instant load)  │
                       │  Expanders       │              └──────────────────┘
                       └──────────────────┘
```

**Secrets Required:**
- `PAT` (Personal Access Token, `repo` + `workflow` scopes) — GitHub Actions only, for checkout+push
- `GITHUB_TOKEN` (Classic PAT, `public_repo` scope) — GitHub Actions only, for API calls
- **No secrets in Streamlit Cloud** — reads static JSON from repo

---

## Quick Start

### Local Development

```bash
# 1. Clone repo
git clone https://github.com/<your-username>/sap-github-repos-finder.git
cd sap-github-repos-finder

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set GitHub token (create at https://github.com/settings/tokens)
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
# Or create .env file from .env.example

# 5. Run fetch script (generates sap_top25.json)
python fetch_sap_repos.py

# 6. Run Streamlit app
streamlit run streamlit_app.py
```

### Deploy to Streamlit Cloud

1. Push this repo to GitHub (public)
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select repo/branch → Main file: `streamlit_app.py`
4. **No secrets needed** in Streamlit Cloud
5. Add `PAT` and `GITHUB_TOKEN` to GitHub repo Settings → Secrets → Actions
6. Deploy — your app will be live at `https://<name>.streamlit.app`

---

## Project Structure

```
sap-github-repos-finder/
├── fetch_sap_repos.py          # Data pipeline: GitHub API → enriched JSON
├── streamlit_app.py            # Streamlit UI: table, filters, expanders, exports
├── requirements.txt            # Python dependencies
├── .env.example                # Local env template
├── .streamlit/
│   └── secrets.toml.example    # Streamlit Cloud secrets template
├── .github/workflows/
│   └── weekly-fetch.yml        # Scheduled GitHub Action
├── sap_top25.json              # Generated data (committed by Action)
├── TODOS.md                    # Implementation task tracker
└── docs/designs/
    └── sap-github-repos-finder.md  # Full design doc
```

---

## SAP Areas Covered

| Area | Description |
|------|-------------|
| ABAP | Core ABAP, ABAP Git, ADT |
| OData | OData V2/V4, SADL, Gateway |
| Fiori | Fiori Elements, Launchpad, Smart Controls |
| UI5 | SAPUI5, OpenUI5, UI5 Tooling, TypeScript |
| Workflow | SAP Workflow, Business Workflow |
| RAP | Restful ABAP Programming, CDS, EML |
| CAP | Cloud Application Programming Model, Node.js, Java |
| S4 Conversion | ECC→S/4HANA, Migration, Greenfield/Brownfield |
| GenAI | Generative AI, LLM, RAG, SAP AI Core, Joule |
| Automation | RPA, iRPA, Build Process Automation |

---

## Data Pipeline (fetch_sap_repos.py)

1. **14 Targeted Search Queries** — Covering all 10 SAP areas
2. **Deduplication** — By `full_name`, first query match wins
3. **README Fetching** — Parallel with caching, rate-limited
4. **Enrichment**:
   - Primary area classification (keyword scoring)
   - Skill extraction (topics + README, 50+ SAP-specific terms)
   - Artifact type detection (starter, sample, SDK, library, tutorial, automation, migration)
   - Purpose & what-it-offers summarization
   - Evidence tracking (matched topics, keywords, queries)
5. **Ranking** — Stars desc, then updated_at desc
6. **Output** — JSON with `generated_at` timestamp + top 25 repos

---

## Configuration

### Search Queries (fetch_sap_repos.py:39-64)
```python
SEARCH_QUERIES = [
    "sap abap in:name,description,readme fork:false sort:stars",
    "topic:abap fork:false sort:stars",
    "sap odata in:name,description,readme fork:false sort:stars",
    "topic:odata sap fork:false sort:stars",
    "sap fiori in:name,description,readme fork:false sort:stars",
    "sap ui5 OR sapui5 OR openui5 in:name,description,readme fork:false sort:stars",
    "topic:sapui5 fork:false sort:stars",
    "sap workflow in:name,description,readme fork:false sort:stars",
    'sap rap OR "restful abap" in:name,description,readme fork:false sort:stars',
    'sap cap OR "cloud application programming model" in:name,description,readme fork:false sort:stars',
    '"ecc" "s4hana" conversion OR transformation in:name,description,readme fork:false sort:stars',
    '"s/4hana" migration OR conversion sap in:name,description,readme fork:false sort:stars',
    'sap "generative ai" OR genai in:name,description,readme fork:false sort:stars',
    'sap ai automation OR "intelligent automation" in:name,description,readme fork:false sort:stars',
]
```

### Rate Limits
- **Search API**: 30 req/min → parallelized with token bucket
- **Core API**: 5000 req/hr → parallelized with token bucket
- **Fetch time**: ~6-10s (parallel) vs 20-40s (sequential)

---

## Testing

```bash
# Install test dependencies
pip install -r requirements-test.txt  # pytest, responses, pytest-cov

# Run tests
pytest tests/ -v --cov=fetch_sap_repos --cov-report=term-missing
```

---

## License

MIT License — Free to use, modify, distribute.

---

## Credits

Built with:
- [GitHub REST API](https://docs.github.com/en/rest)
- [Streamlit](https://streamlit.io)
- [pandas](https://pandas.pydata.org)
- [requests](https://requests.readthedocs.io)

Design inspired by the need for a **curated, discoverable SAP GitHub resource** — no more manual searching, no more sifting through thousands of unclassified results.