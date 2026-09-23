# TODOS — SAP GitHub Repos Finder

Generated from engineering review completion (2026-09-23)

---

## Phase 0: Fetch Script Improvements (from Code Quality + Performance Reviews)

### Critical (Do First)
- [ ] **Add request timeouts** to all `session.request` calls (line 145) — `timeout=30`
- [ ] **Add search rate limit handling** in `_request_with_backoff` for `/search/repositories` 403
- [ ] **Parallelize search queries** with `ThreadPoolExecutor` + token bucket (30 req/min)
- [ ] **Parallelize repo detail fetches** with `ThreadPoolExecutor` + core rate limiter (5000/hr)

### High Priority
- [ ] **Extract config to `config.py`** — move `SEARCH_QUERIES`, `SAP_AREA_KEYWORDS`, `SAP_OFFICIAL_ORGS`, constants
- [ ] **Unify keyword scanning** — single `scan_keywords(text, keyword_map)` utility used by `infer_primary_area` + `build_evidence`
- [ ] **Unify skill definitions** — single source for `skill_keywords` + `area_skills`
- [ ] **Refactor `summarize_readme`** — simpler heuristic: first 3 non-heading paragraphs, artifact type from keywords
- [ ] **Replace `ReadmeCache`** with `functools.lru_cache` + TTL on `get_readme`
- [ ] **Add type hints** to all public function signatures

### Medium Priority
- [ ] **Composite ranking score** — `stars*0.6 + forks*0.2 + recency*0.2` in `rank_repositories`
- [ ] **Position-weighted area inference** — title/description weighted higher than README body
- [ ] **SAP_OFFICIAL_ORGS boost** in `infer_primary_area` (currently defined but unused)
- [ ] **Make column widths dynamic** in `print_table` based on content

### Low Priority / Nice to Have
- [ ] **Add `generated_at` field** to JSON output (ISO 8601 UTC) — wrapper object not raw array
- [ ] **Validate API response structure** — required keys check before `.get()`
- [ ] **Specific exception handling** — replace broad `Exception` catches
- [ ] **Cache write error handling** — log and continue

---

## Phase 1: Streamlit App (`streamlit_app.py`)

### Core UI
- [ ] **Load JSON** with `@st.cache_data` — read `sap_top25.json`
- [ ] **Error handling** — missing file, corrupted JSON, empty data
- [ ] **Header** — title + "Last updated: {timestamp from JSON `generated_at` or file mtime}"
- [ ] **Sidebar filters**:
  - [ ] Multiselect "Filter by SAP Area" (10 areas + "Other")
  - [ ] Text input "Search skills/keywords" (filters `skills`, `what_it_offers`, `purpose`, `topics`)
  - [ ] Download buttons: "Export CSV (filtered)", "Export JSON (filtered)"
- [ ] **Main table** — `st.dataframe` with columns:
  - Rank, Repo (link), Stars, Primary Area, What It Offers, Skills (truncated +N), Purpose, Updated
- [ ] **Row click → expander** below table with:
  - README snippet (first 500 chars)
  - Topics as badge chips
  - Evidence: Matched Topics, Matched Keywords (with area prefix), Matched Queries, README Used
  - "Open on GitHub" button/link
- [ ] **Responsive layout** — sidebar stacks above table on mobile

### Data Processing
- [ ] **Filter logic** — area multiselect + keyword search (case-insensitive, OR across fields)
- [ ] **Export logic** — filtered rows only, CSV/JSON
- [ ] **Skills display** — truncate to 5 + "+N more" tooltip/expander

---

## Phase 2: GitHub Action (`.github/workflows/weekly-fetch.yml`)

- [ ] **Workflow file** with:
  - Cron: `0 6 * * 1` (Monday 6 AM UTC)
  - `fetch-depth: 1` for speed
  - Python 3.11 setup with pip cache
  - Install `requests` from `requirements.txt`
  - Run `python fetch_sap_repos.py` with `GITHUB_TOKEN` secret
  - Commit `sap_top25.json` if changed (with `generated_at` field)
  - Push to trigger Streamlit Cloud redeploy
- [ ] **Permissions**: `contents: write` for checkout + commit
- [ ] **Error handling** — continue-on-error: false, optional failure notification

---

## Phase 3: Configuration & Deployment

### Files to Create
- [ ] `.streamlit/secrets.toml.example` — template (empty for this app — no secrets needed in Streamlit Cloud)
- [ ] `.env.example` — `GITHUB_TOKEN=`
- [ ] `requirements.txt` — add `streamlit>=1.28.0`, `pandas>=2.0.0`

### Git & Deploy
- [ ] `git init` + `git add .` + `git commit`
- [ ] Create GitHub repo (public)
- [ ] Push to GitHub
- [ ] Add `GITHUB_TOKEN` (classic PAT, `public_repo` scope) to GitHub Actions secrets
- [ ] Connect repo to Streamlit Cloud
- [ ] Deploy — verify public URL works

---

## Phase 4: Testing (from Test Review)

### Unit Tests (Pure Functions) — 80 cases
- [ ] `tests/unit/test_infer_primary_area.py` (15)
- [ ] `tests/unit/test_extract_skills.py` (20)
- [ ] `tests/unit/test_summarize_readme.py` (12)
- [ ] `tests/unit/test_build_evidence.py` (10)
- [ ] `tests/unit/test_rank_repositories.py` (8)
- [ ] `tests/unit/test_process_repositories.py` (10)
- [ ] `tests/unit/test_is_relevant.py` (5)

### Integration Tests — 25 cases
- [ ] `tests/integration/test_github_client.py` (12)
- [ ] `tests/integration/test_readme_cache.py` (5)
- [ ] `tests/integration/test_fetch_all_candidates.py` (5)
- [ ] `tests/integration/test_fetch_readmes.py` (3)

### Test Infrastructure
- [ ] `tests/conftest.py` — fixtures
- [ ] `tests/fixtures/github_responses.py` — JSON fixtures
- [ ] `requirements-test.txt` — `pytest`, `responses`, `pytest-cov`
- [ ] `.github/workflows/test.yml` — CI pipeline with coverage gate (≥72%)

---

## Phase 5: Documentation

- [ ] Update `README.md` with project description, usage, deployment guide
- [ ] Document JSON schema in design doc (already done)
- [ ] Add architecture diagram to design doc (ASCII)

---

## Phase 6: Optional Enhancements (Post-v1)

- [ ] Historical trends tracking (stars over time) — v2
- [ ] "Refresh now" button triggering Action via API — v2
- [ ] More SAP areas / search queries based on usage
- [ ] Dark mode toggle in Streamlit
- [ ] Repo detail: file tree via GitHub API

---

## Progress Tracking

| Phase | Status | Items | Done |
|-------|--------|-------|------|
| 0: Fetch Improvements | 🔄 In Progress | 15 | 0 |
| 1: Streamlit App | ⏳ Pending | 12 | 0 |
| 2: GitHub Action | ⏳ Pending | 8 | 0 |
| 3: Config & Deploy | ⏳ Pending | 8 | 0 |
| 4: Testing | ⏳ Pending | 18 | 0 |
| 5: Documentation | ⏳ Pending | 3 | 0 |
| 6: Enhancements | 📋 Backlog | 5 | 0 |

---

## Decision Log (from reviews)

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Split Architecture (Approach C) | Zero API calls on page load, free hosting, weekly freshness |
| D2 | PAT + GITHUB_TOKEN dual secret | PAT for checkout+push (triggers deploy), GITHUB_TOKEN for API calls |
| D3 | `generated_at` in JSON wrapper | Reliable freshness display, not dependent on file mtime |
| D4 | `@st.cache_data` on JSON load | Instant page loads, no re-fetch on interaction |
| D5 | Explicit Action permissions | `contents: write` for commit+push |
| D6 | ASCII diagram in design doc | Architecture visualization for maintainers |
| D7 | Parallelize fetch with rate limiters | 4-6x speedup, respects GitHub limits |
| D8 | Pure functions first for testing | 7/20 units pure — high testability, low mocking |

---

*Last updated: 2026-09-23 | Engineering review complete (Sections 1-4)*