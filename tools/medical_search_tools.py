"""
Medical knowledge search tools — powered by NCBI PubMed (free, no API key required).

Two tools are exposed:
  - search_pubmed          : Full-text search of 35+ million biomedical articles.
  - get_clinical_guidelines: Searches specifically for clinical practice guidelines.

Results include title, authors, journal, year, abstract and a direct PubMed URL
so the doctor can cite or drill into any article.
"""

import json
import urllib.parse
import urllib.request
from typing import Optional

from cache.decorators import cached
from cache.keys import clinical_guidelines_key, is_json_success, pubmed_search_key

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_PUBMED_ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/"


def _ncbi_get(url: str, params: dict) -> dict:
    """Perform a GET request to an NCBI E-utilities endpoint and return parsed JSON."""
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url,
        headers={"User-Agent": "vClinic/1.0 (contact: vclinic@example.com)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_abstracts(pmids: list[str]) -> dict[str, str]:
    """Fetch plain-text abstracts for a list of PubMed IDs."""
    if not pmids:
        return {}
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
    }
    full_url = f"{_EFETCH_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url,
        headers={"User-Agent": "vClinic/1.0 (contact: vclinic@example.com)"},
    )
    # Parse abstract text from XML using simple string extraction (no lxml dep)
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml = resp.read().decode("utf-8")

    abstracts: dict[str, str] = {}
    # Extract <PMID> and <AbstractText> pairs
    import re
    pmid_blocks = re.findall(
        r"<PubmedArticle>(.*?)</PubmedArticle>", xml, re.DOTALL
    )
    for block in pmid_blocks:
        pmid_match = re.search(r"<PMID[^>]*>(\d+)</PMID>", block)
        abstract_parts = re.findall(
            r"<AbstractText[^>]*>(.*?)</AbstractText>", block, re.DOTALL
        )
        if pmid_match:
            pmid = pmid_match.group(1)
            # Strip any nested XML tags
            text = " ".join(
                re.sub(r"<[^>]+>", "", part) for part in abstract_parts
            ).strip()
            abstracts[pmid] = text or "No abstract available."
    return abstracts


def _run_search(query: str, max_results: int) -> list[dict]:
    """Core search logic shared by both tools."""
    max_results = max(1, min(max_results, 10))  # clamp 1–10

    # Step 1: search for matching PMIDs
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    search_data = _ncbi_get(_ESEARCH_URL, search_params)
    pmids: list[str] = search_data.get("esearchresult", {}).get("idlist", [])
    if not pmids:
        return []

    # Step 2: fetch summaries (title, authors, journal, year)
    summary_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    summary_data = _ncbi_get(_ESUMMARY_URL, summary_params)
    result_map = summary_data.get("result", {})

    # Step 3: fetch abstracts
    abstracts = _fetch_abstracts(pmids)

    articles = []
    for pmid in pmids:
        item = result_map.get(pmid, {})
        if not item:
            continue
        authors = ", ".join(
            a.get("name", "") for a in item.get("authors", [])[:3]
        )
        if len(item.get("authors", [])) > 3:
            authors += " et al."
        articles.append(
            {
                "pmid": pmid,
                "title": item.get("title", ""),
                "authors": authors,
                "journal": item.get("fulljournalname", item.get("source", "")),
                "year": item.get("pubdate", "")[:4],
                "abstract": abstracts.get(pmid, "No abstract available."),
                "url": f"{_PUBMED_ARTICLE_URL}{pmid}/",
            }
        )
    return articles


@cached(
    namespace="pubmed_search",
    key_fn=lambda query, max_results=5, **_: pubmed_search_key(query, max_results),
    should_cache=is_json_success,
)
def search_pubmed(query: str, max_results: int = 5) -> str:
    """Search PubMed for recent biomedical literature relevant to a clinical query.

    Use this to look up current evidence on diagnoses, treatments, drug interactions,
    or any clinical question where up-to-date published research is needed.

    Args:
        query:       Free-text search query (e.g. "community acquired pneumonia treatment 2024").
        max_results: Number of articles to return (1–10, default 5).

    Returns:
        JSON string — list of articles with title, authors, journal, year,
        abstract (truncated to 400 chars), and PubMed URL.
    """
    try:
        articles = _run_search(query, max_results)
        if not articles:
            return json.dumps({"results": [], "message": "No articles found for this query."})
        # Truncate abstracts to keep responses concise
        for a in articles:
            if len(a["abstract"]) > 400:
                a["abstract"] = a["abstract"][:397] + "..."
        return json.dumps({"results": articles}, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@cached(
    namespace="clinical_guidelines",
    key_fn=lambda condition, max_results=5, **_: clinical_guidelines_key(condition, max_results),
    should_cache=is_json_success,
)
def get_clinical_guidelines(condition: str, max_results: int = 5) -> str:
    """Search PubMed specifically for clinical practice guidelines on a condition.

    Use this when you need evidence-based recommendations (dosing, screening
    thresholds, staging criteria, preferred treatments) from major medical societies.

    Args:
        condition:   Disease or condition (e.g. "type 2 diabetes", "community acquired pneumonia").
        max_results: Number of guidelines to return (1–10, default 5).

    Returns:
        JSON string — list of guideline articles with title, authors, journal, year,
        abstract (truncated to 400 chars), and PubMed URL.
    """
    # Append a filter so PubMed ranks practice guidelines higher
    query = f"{condition} [Title/Abstract] AND (guideline[pt] OR practice guideline[pt] OR clinical practice guideline)"
    try:
        articles = _run_search(query, max_results)
        if not articles:
            # Fallback: broader search without publication-type filter
            articles = _run_search(f"{condition} clinical guidelines", max_results)
        if not articles:
            return json.dumps({"results": [], "message": "No guidelines found for this condition."})
        for a in articles:
            if len(a["abstract"]) > 400:
                a["abstract"] = a["abstract"][:397] + "..."
        return json.dumps({"results": articles}, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
