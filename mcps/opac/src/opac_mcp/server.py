"""FastMCP server for querying an aDISWeb OPAC library catalog.

Provides tools for searching an aDISWeb OPAC (e.g. the BSZ/IBS service), navigating
results, and retrieving detailed metadata for catalog items.

Runs as an HTTP server (streamable HTTP transport) for production deployment.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from .client import (
    AVAILABILITY,
    BASE_URL,
    EXPORT_FORMATS,
    LANGUAGES,
    MEDIA_TYPES,
    NEW_ACQUISITIONS,
    OPERATORS,
    SEARCH_CATEGORIES,
    SEARCH_SCOPES,
    SORT_OPTIONS,
    START_PARAMS,
    OPACClient,
)

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Server configuration from environment
SERVER_HOST = os.getenv("MCP_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("MCP_PORT", "8000"))

# Institution-specific wording for the model. Set via env.
CATALOG_NAME = os.getenv("OPAC_CATALOG_NAME") or "the library catalog"
CATALOG_FOCUS = (
    os.getenv("OPAC_CATALOG_FOCUS")
    or "books, journals, exhibition catalogs, e-books, films, audio recordings, and more"
)


@asynccontextmanager
async def lifespan(app: FastMCP):
    """Manage server lifecycle - startup and shutdown."""
    logger.info("OPAC MCP server starting up")
    logger.info(f"Listening on {SERVER_HOST}:{SERVER_PORT}")
    yield
    logger.info("OPAC MCP server shutting down")
    # Clean up client if initialized
    global _client
    if _client is not None:
        try:
            _client.close()
            logger.info("OPAC client closed")
        except Exception as e:
            logger.warning(f"Error closing OPAC client: {e}")
        _client = None


mcp = FastMCP(
    "opac",
    instructions=(
        f"OPAC library catalog search for {CATALOG_NAME}. "
        "Use 'opac_search' for quick free-text searches across all fields. "
        "Use 'opac_advanced_search' to search specific fields (author, title, subject, "
        "ISBN, etc.) with boolean operators and filters for media type, language, year, "
        "new acquisitions, availability, volume/issue/edition. "
        "Use 'opac_get_details' to retrieve full metadata for a specific item. "
        "Use 'opac_next_page' / 'opac_previous_page' to navigate result pages. "
        "Use 'opac_sort_results' to re-sort results by relevance, title, author, or year. "
        "Use 'opac_export_results' or 'opac_export_item' to export citations in BibTeX, "
        "Zotero, EndNote, and other formats. "
        "Use 'opac_next_record' / 'opac_previous_record' to step through items on the "
        "detail page without returning to the list. "
        "Use 'opac_back_to_results' to return to the list after viewing details. "
        f"The catalog contains {CATALOG_FOCUS}."
    ),
    lifespan=lifespan,
)

@mcp.custom_route("/health", methods=["GET", "HEAD"])
async def health(_: Request) -> PlainTextResponse:
    """Liveness probe for the Docker HEALTHCHECK."""
    return PlainTextResponse("ok")


# Global client instance (stateful - maintains OPAC session)
_client: OPACClient | None = None


def _get_client() -> OPACClient:
    global _client
    if _client is None:
        _client = OPACClient()
    return _client


@mcp.tool()
def opac_search(query: str, scope: str = "all") -> dict[str, Any]:
    """Search the library catalog with a free-text query.

    Searches across all fields (title, author, subject, etc.) using the
    library's built-in relevance ranking. Supports word stemming (e.g.,
    "Kunst" also finds "Künste"). Use quotes for exact phrases.

    Use '*' for right truncation (e.g., "Sozial*" finds "Sozialwissenschaft").

    Args:
        query: Search terms (e.g., "Medienkunst", "Peter Weibel", "digital art").
        scope: Search scope. One of:
            - "all": All holdings including interlibrary loan
            - "library": Only items in the library's own collection
            - "interlibrary": Only interlibrary loan items

    Returns:
        Search results with total count, current page items, and pagination info.
        Each result includes: item_id, title, year, author, media_type, availability.
    """
    client = _get_client()
    try:
        response = client.search(query, scope=scope)
        result = response.to_dict()
        result["opac_link"] = client.get_search_link(query)
        return result
    except Exception as e:
        logger.exception("Search failed")
        return {"error": str(e), "opac_link": client.get_search_link(query)}


@mcp.tool()
def opac_advanced_search(
    field1_category: str = "title_word",
    field1_term: str = "",
    field2_category: str = "",
    field2_term: str = "",
    field2_operator: str = "and",
    field3_category: str = "",
    field3_term: str = "",
    field3_operator: str = "and",
    field4_category: str = "",
    field4_term: str = "",
    field4_operator: str = "and",
    media_type: str = "all",
    language: str = "all",
    publisher: str = "",
    place: str = "",
    year_exact: str = "",
    year_from: str = "",
    year_to: str = "",
    scope: str = "all",
    new_acquisitions: str = "all",
    availability: str = "all",
    volume: str = "",
    issue: str = "",
    edition: str = "",
) -> dict[str, Any]:
    """Advanced search with specific field categories and filters.

    Supports up to 4 search fields combined with boolean operators,
    plus filters for media type, language, year, publisher, place,
    new acquisitions, availability, and volume/issue/edition.

    Available search categories (use these as field_category values):
        - "title_word": Word in title
        - "title_exact": Exact title match
        - "title_start": Title begins with
        - "author": Author (person)
        - "subject": Subject heading (Schlagwort)
        - "isbn": ISBN, ISSN, or SWB number
        - "institution": Institution/organization
        - "classification": Classification code
        - "signature": Call number (Signatur)
        - "about_person": About a person
        - "about_institution": About an institution

    Available media types:
        "all", "book", "ebook", "journal", "ejournal", "article",
        "exhibition_catalog", "film", "evideo", "audio", "thesis",
        "electronic", "data_carrier"

    Available languages:
        "all", "german", "english", "french", "italian", "spanish"

    Boolean operators: "and", "or", "not"

    New acquisitions: "all", "1_week", "1_month", "2_months", "4_months"

    Availability: "all", "loanable" (only items available for borrowing)

    Args:
        field1_category: Search category for field 1 (default: "title_word").
        field1_term: Search term for field 1.
        field2_category: Category for field 2 (empty to skip).
        field2_term: Search term for field 2.
        field2_operator: Boolean operator between field 1 and 2.
        field3_category: Category for field 3 (empty to skip).
        field3_term: Search term for field 3.
        field3_operator: Boolean operator connecting to field 3.
        field4_category: Category for field 4 (empty to skip).
        field4_term: Search term for field 4.
        field4_operator: Boolean operator connecting to field 4.
        media_type: Filter by media type.
        language: Filter by language.
        publisher: Filter by publisher name.
        place: Filter by place of publication.
        year_exact: Filter by exact year.
        year_from: Start of year range.
        year_to: End of year range.
        scope: "all", "library", or "interlibrary".
        new_acquisitions: Filter to recent acquisitions only.
        availability: Filter to loanable items only.
        volume: Volume number (for journals/series).
        issue: Issue number (for journals).
        edition: Edition number.

    Returns:
        Search results with metadata, pagination info, and OPAC link.
    """
    client = _get_client()
    try:
        response = client.advanced_search(
            field1_category=field1_category,
            field1_term=field1_term,
            field2_category=field2_category,
            field2_term=field2_term,
            field2_operator=field2_operator,
            field3_category=field3_category,
            field3_term=field3_term,
            field3_operator=field3_operator,
            field4_category=field4_category,
            field4_term=field4_term,
            field4_operator=field4_operator,
            media_type=media_type,
            language=language,
            publisher=publisher,
            place=place,
            year_exact=year_exact,
            year_from=year_from,
            year_to=year_to,
            scope=scope,
            new_acquisitions=new_acquisitions,
            availability=availability,
            volume=volume,
            issue=issue,
            edition=edition,
        )
        result = response.to_dict()
        result["opac_link"] = client.get_search_link("")
        return result
    except Exception as e:
        logger.exception("Advanced search failed")
        return {"error": str(e), "opac_link": client.get_search_link("")}


@mcp.tool()
def opac_get_details(item_id: str) -> dict[str, Any]:
    """Get detailed metadata for a specific catalog item.

    Retrieves full bibliographic data including title, author, publisher,
    year, ISBN, subject headings, classification, and holding/availability
    information. Must be called after a search when results are displayed.

    Args:
        item_id: The item identifier from search results (e.g., "AK62937472").

    Returns:
        Detailed metadata with fields like Titel, Person, Veröffentlichung,
        ISBN, Schlagwortfolge, etc., plus holdings with location and availability.
    """
    client = _get_client()
    try:
        detail = client.get_item_details(item_id)
        return detail.to_dict()
    except Exception as e:
        logger.exception("Get details failed")
        return {"error": str(e)}


@mcp.tool()
def opac_next_page() -> dict[str, Any]:
    """Navigate to the next page of search results.

    Each page shows approximately 20 results. Call this after a search
    to see more results.

    Returns:
        Next page of search results.
    """
    client = _get_client()
    try:
        response = client.next_page()
        return response.to_dict()
    except Exception as e:
        logger.exception("Next page failed")
        return {"error": str(e)}


@mcp.tool()
def opac_previous_page() -> dict[str, Any]:
    """Navigate to the previous page of search results.

    Returns:
        Previous page of search results.
    """
    client = _get_client()
    try:
        response = client.previous_page()
        return response.to_dict()
    except Exception as e:
        logger.exception("Previous page failed")
        return {"error": str(e)}


@mcp.tool()
def opac_back_to_results() -> dict[str, Any]:
    """Return to the search results list after viewing item details.

    Call this after opac_get_details to go back to the result list
    for further browsing.

    Returns:
        Current page of search results.
    """
    client = _get_client()
    try:
        response = client.back_to_results()
        return response.to_dict()
    except Exception as e:
        logger.exception("Back to results failed")
        return {"error": str(e)}


@mcp.tool()
def opac_sort_results(sort_by: str = "relevance") -> dict[str, Any]:
    """Sort the current search results.

    Re-sorts results on the current page. Note: sorting may not be available
    for very large result sets (the OPAC limits sorting to manageable sizes).

    Args:
        sort_by: Sort option. One of:
            - "relevance": Sort by search relevance (default)
            - "title": Sort alphabetically by title
            - "author": Sort alphabetically by author
            - "year_desc": Sort by year, newest first
            - "year_asc": Sort by year, oldest first

    Returns:
        Re-sorted search results.
    """
    client = _get_client()
    try:
        response = client.sort_results(sort_by)
        return response.to_dict()
    except Exception as e:
        logger.exception("Sort failed")
        return {"error": str(e)}


@mcp.tool()
def opac_export_results(format: str = "bibtex") -> dict[str, Any]:
    """Export current search results as citation data.

    Exports up to 300 titles from the current result set in a standard
    citation format. Useful for importing into reference managers.

    Args:
        format: Citation format. One of:
            - "bibtex": BibTeX format (for LaTeX, JabRef, etc.)
            - "zotero": Zotero RIS format
            - "endnote": EndNote format
            - "citavi": Citavi format
            - "procite": ProCite format
            - "refworks": RefWorks format
            - "reference_manager": Reference Manager format

    Returns:
        Dictionary with "citation_data" containing the formatted citations.
    """
    client = _get_client()
    try:
        data = client.export_results(format)
        return {"citation_data": data, "format": format}
    except Exception as e:
        logger.exception("Export results failed")
        return {"error": str(e)}


@mcp.tool()
def opac_export_item(format: str = "bibtex") -> dict[str, Any]:
    """Export the currently viewed item as citation data.

    Must be called while viewing item details (after opac_get_details).

    Args:
        format: Citation format. One of:
            - "bibtex": BibTeX format
            - "zotero": Zotero RIS format
            - "endnote": EndNote format
            - "citavi": Citavi format
            - "procite": ProCite format
            - "refworks": RefWorks format
            - "reference_manager": Reference Manager format

    Returns:
        Dictionary with "citation_data" containing the formatted citation.
    """
    client = _get_client()
    try:
        data = client.export_item(format)
        return {"citation_data": data, "format": format}
    except Exception as e:
        logger.exception("Export item failed")
        return {"error": str(e)}


@mcp.tool()
def opac_next_record() -> dict[str, Any]:
    """Navigate to the next record while on the detail page.

    Steps forward through the result list without going back to
    the results page first. Useful for quickly reviewing several items.

    Returns:
        Detailed metadata for the next item in the result list.
    """
    client = _get_client()
    try:
        detail = client.next_record()
        return detail.to_dict()
    except Exception as e:
        logger.exception("Next record failed")
        return {"error": str(e)}


@mcp.tool()
def opac_previous_record() -> dict[str, Any]:
    """Navigate to the previous record while on the detail page.

    Steps backward through the result list without going back to
    the results page first.

    Returns:
        Detailed metadata for the previous item in the result list.
    """
    client = _get_client()
    try:
        detail = client.previous_record()
        return detail.to_dict()
    except Exception as e:
        logger.exception("Previous record failed")
        return {"error": str(e)}


@mcp.tool()
def opac_search_options() -> dict[str, Any]:
    """Get available search categories, media types, and languages.

    Use this to discover what options are available for advanced search.

    Returns:
        Dictionary with available categories, media_types, languages,
        operators, and scopes.
    """
    return {
        "search_categories": SEARCH_CATEGORIES,
        "media_types": MEDIA_TYPES,
        "languages": LANGUAGES,
        "operators": OPERATORS,
        "scopes": SEARCH_SCOPES,
        "new_acquisitions": NEW_ACQUISITIONS,
        "availability": AVAILABILITY,
        "sort_options": list(SORT_OPTIONS.keys()),
        "export_formats": list(EXPORT_FORMATS.keys()),
        "catalog_name": CATALOG_NAME,
        "catalog_url": f"{BASE_URL}?{START_PARAMS}",
    }


def main():
    """Run the MCP server in HTTP mode."""
    logger.info(f"Starting OPAC MCP server on http://{SERVER_HOST}:{SERVER_PORT}")
    mcp.run(
        transport="streamable-http",
        host=SERVER_HOST,
        port=SERVER_PORT,
    )


if __name__ == "__main__":
    main()
