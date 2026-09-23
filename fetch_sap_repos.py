#!/usr/bin/env python3
"""
fetch_sap_repos.py - Fetch top 25 SAP-related GitHub repositories

Usage:
    export GITHUB_TOKEN="your_github_token"
    python fetch_sap_repos.py

Outputs:
    - Human-readable table to stdout
    - JSON file: sap_top25.json

Requires:
    - Python 3.8+
    - requests library: pip install requests
"""

import os
import sys
import json
import time
import base64
import logging
import threading
from datetime import datetime
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

GITHUB_API_BASE = "https://api.github.com"
SEARCH_QUERIES = [
    # ABAP
    "sap abap in:name,description,readme fork:false sort:stars",
    "topic:abap fork:false sort:stars",
    # OData
    "sap odata in:name,description,readme fork:false sort:stars",
    "topic:odata sap fork:false sort:stars",
    # Fiori
    "sap fiori in:name,description,readme fork:false sort:stars",
    # UI5 / OpenUI5
    "sap ui5 OR sapui5 OR openui5 in:name,description,readme fork:false sort:stars",
    "topic:sapui5 fork:false sort:stars",
    # Workflow
    "sap workflow in:name,description,readme fork:false sort:stars",
    # RAP
    'sap rap OR "restful abap" in:name,description,readme fork:false sort:stars',
    # CAP
    'sap cap OR "cloud application programming model" in:name,description,readme fork:false sort:stars',
    # S/4HANA Conversion
    '"ecc" "s4hana" conversion OR transformation in:name,description,readme fork:false sort:stars',
    '"s/4hana" migration OR conversion sap in:name,description,readme fork:false sort:stars',
    # Generative AI
    'sap "generative ai" OR genai in:name,description,readme fork:false sort:stars',
    # AI Automation
    'sap ai automation OR "intelligent automation" in:name,description,readme fork:false sort:stars',
]

# SAP area keywords for classification
SAP_AREA_KEYWORDS = {
    "ABAP": ["abap", "abapgit", "abap-restful", "rap", "cds", "core data services"],
    "OData": ["odata", "o data", "odata v2", "odata v4", "odata service"],
    "Fiori": ["fiori", "fiori elements", "fiori launchpad", "smart template"],
    "UI5": ["ui5", "sapui5", "openui5", "sap ui5", "ui5 framework", "ui5 tooling"],
    "Workflow": ["workflow", "workflow management", "sap workflow", "business workflow"],
    "RAP": ["rap", "restful abap", "restful application programming"],
    "CAP": ["cap", "cloud application programming model", "cds", "cap node.js", "cap java"],
    "S4 Conversion": ["s/4hana", "s4hana", "ecc", "conversion", "transformation", "migration", "greenfield", "brownfield", "bluefield"],
    "GenAI": ["generative ai", "genai", "llm", "large language model", "joule", "ai core", "foundation model"],
    "Automation": ["intelligent automation", "ai automation", "rpa", "process automation", "build process automation"],
}

# Official SAP orgs to prefer
SAP_OFFICIAL_ORGS = {"SAP", "SAP-samples", "SAP-samples-cloud", "SAP-samples-s4hana", "SAP-samples-abap"}

PER_PAGE = 100
MIN_CANDIDATES = 100
TOP_N = 25
README_CACHE_DIR = ".readme_cache"

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Repository:
    full_name: str
    html_url: str
    description: Optional[str]
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    language: Optional[str]
    topics: List[str]
    updated_at: str
    primary_area: str = ""
    what_it_offers: str = ""
    skills: List[str] = None
    purpose: str = ""
    evidence: Dict = None

    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.evidence is None:
            self.evidence = {}

# ============================================================================
# GITHUB API CLIENT
# ============================================================================

class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "fetch-sap-repos/1.0"
        })
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0

    def _check_rate_limit(self, response: requests.Response):
        """Update rate limit info from response headers."""
        self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", 5000))
        self.rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", 0))
        if self.rate_limit_remaining < 10:
            reset_in = max(self.rate_limit_reset - time.time(), 0)
            logger.warning(f"Rate limit low: {self.rate_limit_remaining} remaining. Reset in {reset_in:.0f}s")

    def _request_with_backoff(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make request with exponential backoff on rate limits."""
        max_retries = 5
        base_delay = 2

        # Add timeout if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30

        for attempt in range(max_retries):
            response = self.session.request(method, url, **kwargs)
            self._check_rate_limit(response)

            if response.status_code == 200:
                return response

            # Search API rate limit (30 req/min) - different from core API
            if response.status_code == 403 and "/search/repositories" in url:
                reset_in = max(self.rate_limit_reset - time.time(), 0) + 5
                logger.warning(f"Search rate limited. Waiting {reset_in:.0f}s...")
                time.sleep(reset_in)
                continue

            if response.status_code == 403 and "rate limit" in response.text.lower():
                reset_in = max(self.rate_limit_reset - time.time(), 0) + 5
                logger.warning(f"Rate limited. Waiting {reset_in:.0f}s...")
                time.sleep(reset_in)
                continue

            if response.status_code == 404:
                return response

            if response.status_code >= 500:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Server error {response.status_code}. Retrying in {delay}s...")
                time.sleep(delay)
                continue

            if response.status_code == 401:
                logger.error("Authentication failed (401). Check GITHUB_TOKEN.")
                response.raise_for_status()

            response.raise_for_status()

        response.raise_for_status()
        return response

    def search_repositories(self, query: str, page: int = 1) -> Dict:
        """Search repositories with pagination."""
        url = f"{GITHUB_API_BASE}/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": PER_PAGE,
            "page": page
        }
        response = self._request_with_backoff("GET", url, params=params)
        return response.json()

    def get_repository(self, owner: str, repo: str) -> Optional[Dict]:
        """Get full repository details including topics."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        response = self._request_with_backoff("GET", url)
        if response.status_code == 404:
            return None
        return response.json()

    def get_readme(self, owner: str, repo: str) -> Optional[str]:
        """Get README content (base64 decoded)."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
        response = self._request_with_backoff("GET", url)
        if response.status_code == 404:
            return None
        data = response.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return data.get("content", "")

# ============================================================================
# README CACHE
# ============================================================================

class ReadmeCache:
    def __init__(self, cache_dir: str = README_CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, owner: str, repo: str) -> str:
        safe_name = f"{owner}_{repo}".replace("/", "_")
        return os.path.join(self.cache_dir, f"{safe_name}.md")

    def get(self, owner: str, repo: str) -> Optional[str]:
        path = self._cache_path(owner, repo)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def set(self, owner: str, repo: str, content: str):
        path = self._cache_path(owner, repo)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


# ============================================================================
# RATE LIMITERS
# ============================================================================

class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate_per_minute: int):
        self.rate_per_second = rate_per_minute / 60.0
        self.capacity = rate_per_minute
        self.tokens = float(rate_per_minute)
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self):
        """Block until a token is available."""
        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    self.last_update = now
                    return
                # Calculate sleep time
                sleep_time = (1.0 - self.tokens) / self.rate_per_second
            time.sleep(min(sleep_time, 1.0))


# Global rate limiters
SEARCH_RATE_LIMITER = TokenBucketRateLimiter(30)   # 30 req/min for search API
CORE_RATE_LIMITER = TokenBucketRateLimiter(5000)   # 5000 req/hr for core API

# ============================================================================
# REPOSITORY PROCESSING
# ============================================================================

def infer_primary_area(repo_data: Dict, readme: Optional[str]) -> str:
    """Infer the primary SAP area from repository data and README."""
    text_parts = [
        repo_data.get("description", "") or "",
        " ".join(repo_data.get("topics", [])),
        readme or ""
    ]
    full_text = " ".join(text_parts).lower()

    scores = {}
    for area, keywords in SAP_AREA_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in full_text)
        if score > 0:
            scores[area] = score

    if scores:
        return max(scores, key=scores.get)
    return "Other"

def extract_skills(topics: List[str], readme: Optional[str], primary_area: str) -> List[str]:
    """Extract skills/technologies from topics and README."""
    skills = set()

    # From topics
    skill_keywords = {
        "ABAP", "CDS", "RAP", "BTP", "CAP", "Node.js", "Java", "OData V2", "OData V4",
        "UI5", "Fiori Elements", "Fiori", "SAP Workflow", "S/4HANA", "Migration",
        "CI/CD", "GitHub Actions", "SAP Build", "SAP AI Core", "Joule", "Embeddings",
        "RAG", "Prompt Engineering", "TypeScript", "JavaScript", "Python", "Go",
        "Docker", "Kubernetes", "Cloud Foundry", "Kyma", "Event Mesh", "SAP HANA"
    }

    text = " ".join(topics).lower()
    if readme:
        text += " " + readme.lower()

    for skill in skill_keywords:
        if skill.lower() in text:
            skills.add(skill)

    # Add area-specific skills
    area_skills = {
        "ABAP": ["ABAP", "CDS", "RAP", "ABAP Git", "ADT"],
        "OData": ["OData V2", "OData V4", "SADL", "Gateway"],
        "Fiori": ["Fiori Elements", "Fiori Launchpad", "Smart Controls", "Annotations"],
        "UI5": ["UI5", "OpenUI5", "UI5 Tooling", "TypeScript", "MVC"],
        "Workflow": ["SAP Workflow", "Business Workflow", "WF-BATCH"],
        "RAP": ["RAP", "CDS", "EML", "Behavior Definitions", "Projections"],
        "CAP": ["CAP", "CDS", "Node.js", "Java", "MTA", "Service Definitions"],
        "S4 Conversion": ["S/4HANA", "Migration", "Code Inspector", "ATC", "Simplification"],
        "GenAI": ["Generative AI", "LLM", "RAG", "Embeddings", "Prompt Engineering", "SAP AI Core"],
        "Automation": ["RPA", "Process Automation", "iRPA", "SAP Build Process Automation"],
    }

    if primary_area in area_skills:
        skills.update(area_skills[primary_area])

    return sorted(list(skills))[:12]

def summarize_readme(readme: Optional[str], description: Optional[str], topics: List[str]) -> tuple:
    """Generate what_it_offers, purpose from README and metadata."""
    if not readme:
        # Fallback to description + topics
        what = description or f"Repository with topics: {', '.join(topics[:5])}"
        purpose = f"Explore {description.lower() if description else 'this SAP-related project'}"
        return what[:160], purpose[:160]

    # Extract first meaningful sections
    lines = readme.split("\n")
    relevant_sections = []
    in_relevant = False

    for line in lines:
        line_lower = line.strip().lower()
        # Start capturing at intro or key sections
        if any(keyword in line_lower for keyword in [
            "## features", "## getting started", "## usage", "## installation",
            "## prerequisites", "## overview", "## introduction", "## what is",
            "## about", "## description", "# features", "# getting started",
            "# usage", "# installation", "# overview"
        ]):
            in_relevant = True
        elif line.startswith("## ") and in_relevant and not any(
            kw in line_lower for kw in ["feature", "start", "usage", "install", "overview", "about"]
        ):
            in_relevant = False

        if in_relevant or (not in_relevant and len(relevant_sections) < 3 and line.strip() and not line.startswith("#")):
            relevant_sections.append(line.strip())

    content = " ".join(relevant_sections[:10])
    if not content:
        content = readme[:500]

    # Determine artifact type
    artifact_indicators = {
        "starter template": ["starter", "template", "boilerplate", "scaffold"],
        "sample app": ["sample", "example", "demo", "reference implementation"],
        "SDK": ["sdk", "client library", "client sdk"],
        "library": ["library", "package", "module", "utility"],
        "tutorial": ["tutorial", "workshop", "guide", "learning", "exercise"],
        "automation scripts": ["script", "automation", "cli tool", "migration tool"],
        "migration tooling": ["migration", "conversion", "transformation", "upgrade"],
    }

    artifact_type = "project"
    content_lower = content.lower()
    for atype, indicators in artifact_indicators.items():
        if any(ind in content_lower for ind in indicators):
            artifact_type = atype
            break

    what_it_offers = f"{artifact_type.title()} for {content[:120]}"
    purpose = f"Use this to {content[:120]}"

    return what_it_offers[:160], purpose[:160]

def build_evidence(repo_data: Dict, readme: Optional[str], matched_queries: List[str]) -> Dict:
    """Build evidence object showing what matched."""
    matched_topics = [t for t in repo_data.get("topics", [])
                      if any(kw in t.lower() for kw in
                             ["sap", "abap", "odata", "fiori", "ui5", "rap", "cap", "hana", "workflow"])]

    matched_keywords = []
    text = f"{repo_data.get('description', '')} {' '.join(repo_data.get('topics', []))}".lower()
    for area, keywords in SAP_AREA_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                matched_keywords.append(f"{area}:{kw}")

    return {
        "matched_topics": matched_topics[:10],
        "matched_keywords": matched_keywords[:10],
        "readme_snippet_used": readme is not None,
        "matched_queries": matched_queries[:5]
    }

# ============================================================================
# MAIN FETCH LOGIC
# ============================================================================

def _search_one_query(query: str, client: GitHubClient) -> tuple:
    """Execute a single search query with rate limiting."""
    SEARCH_RATE_LIMITER.acquire()
    logger.info(f"Searching: {query[:60]}...")
    try:
        result = client.search_repositories(query, page=1)
        items = result.get("items", [])
        logger.info(f"  Found {len(items)} repos")
        return query, items, None
    except Exception as e:
        logger.error(f"Query failed: {query} - {e}")
        return query, [], e


def _fetch_repo_details(full_name: str, client: GitHubClient) -> tuple:
    """Fetch full repository details with rate limiting."""
    CORE_RATE_LIMITER.acquire()
    owner, repo = full_name.split("/")
    details = client.get_repository(owner, repo)
    return full_name, details


def fetch_all_candidates(client: GitHubClient, cache: ReadmeCache) -> List[Repository]:
    """Fetch candidates from all search queries in parallel."""
    all_repos = {}
    query_stats = {}

    # Phase 1: Parallel search queries
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_search_one_query, q, client): q for q in SEARCH_QUERIES}
        for future in as_completed(futures):
            query, items, error = future.result()
            query_stats[query] = len(items)
            if error:
                continue

            for item in items:
                full_name = item["full_name"]
                if full_name not in all_repos:
                    all_repos[full_name] = item
                    if "_matched_queries" not in all_repos[full_name]:
                        all_repos[full_name]["_matched_queries"] = []
                    all_repos[full_name]["_matched_queries"].append(query)

    logger.info(f"Total unique repos after search dedup: {len(all_repos)}")
    logger.info(f"Per-query counts: {query_stats}")

    # Phase 2: Parallel repo detail fetches (only for repos we don't have full details for)
    repos_needing_details = {fn: rd for fn, rd in all_repos.items() if "topics" not in rd}
    if repos_needing_details:
        logger.info(f"Fetching details for {len(repos_needing_details)} repos...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_fetch_repo_details, fn, client): fn for fn in repos_needing_details}
            for future in as_completed(futures):
                full_name, details = future.result()
                if details:
                    # Preserve matched_queries
                    matched_queries = all_repos[full_name].get("_matched_queries", [])
                    all_repos[full_name] = details
                    if "_matched_queries" not in all_repos[full_name]:
                        all_repos[full_name]["_matched_queries"] = []
                    all_repos[full_name]["_matched_queries"].extend(matched_queries)

    logger.info(f"Total unique repos after detail fetch: {len(all_repos)}")
    return list(all_repos.values())

def _fetch_one_readme(full_name: str, client: GitHubClient, cache: ReadmeCache) -> tuple:
    """Fetch a single README with rate limiting."""
    CORE_RATE_LIMITER.acquire()
    owner, name = full_name.split("/")

    # Try cache first
    readme = cache.get(owner, name)
    if readme is not None:
        return full_name, readme, True  # cached

    # Fetch from API
    readme = client.get_readme(owner, name)
    if readme:
        cache.set(owner, name, readme)
    return full_name, readme, False  # not cached


def fetch_readmes(client: GitHubClient, cache: ReadmeCache, repos: List[Dict]) -> Dict[str, Optional[str]]:
    """Fetch READMEs for all repositories in parallel."""
    readmes = {}
    success = 0
    cached = 0

    full_names = [repo["full_name"] for repo in repos]

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_one_readme, fn, client, cache): fn for fn in full_names}
        for future in as_completed(futures):
            full_name, readme, was_cached = future.result()
            readmes[full_name] = readme
            if readme:
                success += 1
            if was_cached:
                cached += 1

    logger.info(f"READMEs fetched: {success}/{len(repos)} (cached: {cached})")
    return readmes

def process_repositories(raw_repos: List[Dict], readmes: Dict[str, Optional[str]]) -> List[Repository]:
    """Process raw repository data into enriched Repository objects."""
    processed = []

    for repo_data in raw_repos:
        full_name = repo_data["full_name"]
        readme = readmes.get(full_name)
        matched_queries = repo_data.get("_matched_queries", [])

        primary_area = infer_primary_area(repo_data, readme)
        skills = extract_skills(repo_data.get("topics", []), readme, primary_area)
        what_it_offers, purpose = summarize_readme(readme, repo_data.get("description"), repo_data.get("topics", []))
        evidence = build_evidence(repo_data, readme, matched_queries)

        repo = Repository(
            full_name=full_name,
            html_url=repo_data["html_url"],
            description=repo_data.get("description"),
            stargazers_count=repo_data["stargazers_count"],
            forks_count=repo_data["forks_count"],
            open_issues_count=repo_data["open_issues_count"],
            language=repo_data.get("language"),
            topics=repo_data.get("topics", []),
            updated_at=repo_data["updated_at"],
            primary_area=primary_area,
            what_it_offers=what_it_offers,
            skills=skills,
            purpose=purpose,
            evidence=evidence
        )
        processed.append(repo)

    return processed

def rank_repositories(repos: List[Repository]) -> List[Repository]:
    """Rank repositories by stars (desc), then by updated_at (desc)."""
    def sort_key(r: Repository):
        updated = datetime.fromisoformat(r.updated_at.replace("Z", "+00:00"))
        return (-r.stargazers_count, -updated.timestamp())

    return sorted(repos, key=sort_key)

def is_relevant(repo: Repository) -> bool:
    """Check if repository matches at least one target SAP area."""
    return repo.primary_area != "Other" or len(repo.evidence.get("matched_keywords", [])) > 0

# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def print_table(repos: List[Repository]):
    """Print human-readable table to stdout."""
    if not repos:
        print("No repositories found.")
        return

    # Column widths
    col_widths = {
        "rank": 4,
        "repo": 45,
        "stars": 6,
        "area": 16,
        "offers": 50,
        "skills": 40,
        "purpose": 45,
        "updated": 12,
    }

    # Header
    header = (f"{'Rank':<{col_widths['rank']}} "
              f"{'Repo':<{col_widths['repo']}} "
              f"{'Stars':>{col_widths['stars']}} "
              f"{'Primary Area':<{col_widths['area']}} "
              f"{'What it offers':<{col_widths['offers']}} "
              f"{'Skills':<{col_widths['skills']}} "
              f"{'Purpose':<{col_widths['purpose']}} "
              f"{'Updated':<{col_widths['updated']}}")
    print(header)
    print("-" * len(header))

    for i, repo in enumerate(repos, 1):
        updated = repo.updated_at[:10]  # YYYY-MM-DD
        skills_str = ", ".join(repo.skills[:5])
        if len(repo.skills) > 5:
            skills_str += f" +{len(repo.skills)-5} more"

        row = (f"{i:<{col_widths['rank']}} "
               f"{repo.full_name:<{col_widths['repo']}} "
               f"{repo.stargazers_count:>{col_widths['stars']}} "
               f"{repo.primary_area:<{col_widths['area']}} "
               f"{repo.what_it_offers:<{col_widths['offers']}} "
               f"{skills_str:<{col_widths['skills']}} "
               f"{repo.purpose:<{col_widths['purpose']}} "
               f"{updated:<{col_widths['updated']}}")
        print(row)

    print(f"\nTotal: {len(repos)} repositories")

def export_json(repos: List[Repository], filename: str = "sap_top25.json"):
    """Export repositories to JSON file with generated_at timestamp."""
    data = []
    for repo in repos:
        data.append(asdict(repo))

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "repos": data
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"JSON exported to {filename}")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    # Check for GITHUB_TOKEN
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set.", file=sys.stderr)
        print("Please set it with: export GITHUB_TOKEN='your_token'", file=sys.stderr)
        print("Create a token at: https://github.com/settings/tokens", file=sys.stderr)
        sys.exit(1)

    logger.info("Starting SAP repository fetch...")
    logger.info(f"Using {len(SEARCH_QUERIES)} search queries")

    client = GitHubClient(token)
    cache = ReadmeCache()

    # Fetch all candidates
    raw_repos = fetch_all_candidates(client, cache)

    if len(raw_repos) < MIN_CANDIDATES:
        logger.warning(f"Only {len(raw_repos)} candidates found (target: {MIN_CANDIDATES})")

    # Fetch READMEs
    readmes = fetch_readmes(client, cache, raw_repos)

    # Process and enrich
    processed = process_repositories(raw_repos, readmes)

    # Filter for relevance
    relevant = [r for r in processed if is_relevant(repo=r)]
    logger.info(f"Relevant repos: {len(relevant)}")

    # Rank and select top 25
    ranked = rank_repositories(relevant)
    top25 = ranked[:TOP_N]

    # Output
    print_table(top25)
    export_json(top25)

    # Summary stats
    area_counts = {}
    for r in top25:
        area_counts[r.primary_area] = area_counts.get(r.primary_area, 0) + 1
    logger.info(f"Area distribution: {area_counts}")
    logger.info("Done!")

if __name__ == "__main__":
    main()