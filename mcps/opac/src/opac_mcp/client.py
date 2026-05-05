"""OPAC client for the BSZ/IBS aDISWeb library catalog system.

Handles session management, search submission, result parsing,
and item detail retrieval by mimicking browser interactions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
from bs4 import BeautifulSoup, Tag


BASE_URL = "https://bsz.ibs-bw.de/aDISWeb/app"
START_PARAMS = "service=direct/0/Home/$DirectLink&sp=SOPAC54"

# Search field categories available in the advanced search
SEARCH_CATEGORIES = {
    "title_word": "Titelwort",
    "title_exact": "Titel präzis",
    "title_start": "Titelanfang",
    "author": "Autor (Person)",
    "subject": "Schlagwort",
    "isbn": "ISSN, ISBN, SWB-Nr.",
    "institution": "Institution",
    "classification": "Klassifikation",
    "signature": "Signatur",
    "reading_room": "Lesesaal-Signatur",
    "about_institution": "Über Institution",
    "about_person": "Über Person",
}

# Media types
MEDIA_TYPES = {
    "all": "- Alle -",
    "article": "Aufsatz",
    "exhibition_catalog": "Ausstellungskatalog",
    "book": "Buch",
    "data_carrier": "Datenträger",
    "ebook": "E-Book",
    "ejournal": "E-Journal",
    "evideo": "E-Video",
    "electronic": "Elektronische Ressource",
    "film": "Filme",
    "thesis": "Hochschulschrift",
    "audio": "Tonträger",
    "journal": "Zeitschrift",
}

# Languages
LANGUAGES = {
    "all": "- Alle -",
    "german": "Deutsch",
    "english": "Englisch",
    "french": "Französisch",
    "italian": "Italienisch",
    "spanish": "Spanisch",
}

# Boolean operators
OPERATORS = {"and": "UND", "or": "ODER", "not": "NICHT"}

# Search scopes
SEARCH_SCOPES = {
    "all": "Alle Bestände",
    "library": "Bibliotheksbestand",
    "interlibrary": "Fernleihe",
}

# New acquisitions timeframes
NEW_ACQUISITIONS = {
    "all": "- Alle -",
    "1_week": "1 Woche",
    "1_month": "1 Monat",
    "2_months": "2 Monate",
    "4_months": "4 Monate",
}

# Availability filter
AVAILABILITY = {
    "all": "- Alle -",
    "loanable": "nur ausleihbare Medien",
}

# Sort options (results page textButton$4-$8)
SORT_OPTIONS = {
    "relevance": ("textButton$4", "Relevanz"),
    "title": ("textButton$5", "Titel"),
    "author": ("textButton$6", "Verfasser"),
    "year_desc": ("textButton$7", "Jahr abwärts"),
    "year_asc": ("textButton$8", "Jahr aufwärts"),
}

# Export formats (results page textButton$9-$15, detail page textButton$1-$7)
EXPORT_FORMATS = {
    "bibtex": "BibTeX",
    "citavi": "Citavi",
    "endnote": "EndNote",
    "procite": "ProCite",
    "refworks": "RefWorks",
    "reference_manager": "Reference Manager",
    "zotero": "Zotero",
}
EXPORT_BUTTONS_RESULTS = {
    "bibtex": "textButton$9",
    "citavi": "textButton$10",
    "endnote": "textButton$11",
    "procite": "textButton$12",
    "refworks": "textButton$13",
    "reference_manager": "textButton$14",
    "zotero": "textButton$15",
}
EXPORT_BUTTONS_DETAIL = {
    "bibtex": "textButton$1",
    "citavi": "textButton$2",
    "endnote": "textButton$3",
    "procite": "textButton$4",
    "refworks": "textButton$5",
    "reference_manager": "textButton$6",
    "zotero": "textButton$7",
}


@dataclass
class SearchResult:
    """A single search result item."""

    item_id: str = ""
    position: int = 0
    title: str = ""
    year: str = ""
    author: str = ""
    contained_in: str = ""
    media_type: str = ""
    availability: str = ""
    signature: str = ""
    cover_url: str = ""
    details: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass
class SearchResponse:
    """Complete search response with results and metadata."""

    query_description: str = ""
    total_results: int = 0
    current_page_results: list[SearchResult] = field(default_factory=list)
    has_next_page: bool = False
    has_previous_page: bool = False
    result_link: str = ""

    def to_dict(self) -> dict:
        return {
            "query_description": self.query_description,
            "total_results": self.total_results,
            "results": [r.to_dict() for r in self.current_page_results],
            "has_next_page": self.has_next_page,
            "has_previous_page": self.has_previous_page,
            "result_link": self.result_link,
        }


@dataclass
class ItemDetail:
    """Detailed metadata for a single catalog item."""

    item_id: str = ""
    title: str = ""
    fields: dict = field(default_factory=dict)
    holdings: list[dict] = field(default_factory=list)
    link: str = ""
    external_links: list[dict] = field(default_factory=list)
    cover_url: str = ""

    def to_dict(self) -> dict:
        result = {
            "item_id": self.item_id,
            "title": self.title,
            "fields": self.fields,
            "holdings": self.holdings,
            "link": self.link,
        }
        if self.external_links:
            result["external_links"] = self.external_links
        if self.cover_url:
            result["cover_url"] = self.cover_url
        return result


class OPACClient:
    """Client for the BSZ/IBS aDISWeb OPAC system.

    Manages HTTP sessions and provides methods for searching the catalog,
    navigating results, and retrieving item details.
    """

    def __init__(self, base_url: str = BASE_URL, start_params: str = START_PARAMS):
        self.base_url = base_url
        self.start_params = start_params
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        )
        self._session_id: str = ""
        self._request_count: int = 0
        self._current_service: str = ""
        self._current_action: str = ""
        self._current_soup: Optional[BeautifulSoup] = None
        self._on_results_page: bool = False
        self._on_detail_page: bool = False
        self._initialized: bool = False

    def _ensure_session(self) -> None:
        """Initialize a session if not already done."""
        if not self._initialized:
            self._init_session()

    def _init_session(self) -> None:
        """Load the OPAC home page and establish a session."""
        resp = self._client.get(f"{self.base_url}?{self.start_params}")
        resp.raise_for_status()
        self._current_soup = BeautifulSoup(resp.text, "lxml")
        self._extract_session_info(self._current_soup)
        self._initialized = True
        self._on_results_page = False
        self._on_detail_page = False

    def _extract_session_info(self, soup: BeautifulSoup) -> None:
        """Extract session ID, service, and form action from a page."""
        form = soup.find("form")
        if form and isinstance(form, Tag):
            action = form.get("action", "")
            if isinstance(action, list):
                action = action[0]
            self._current_action = str(action)
            sid_match = re.search(r"jsessionid=([0-9A-Fa-f]+)", self._current_action)
            if sid_match:
                self._session_id = sid_match.group(1)

        service_input = soup.find("input", {"name": "service"})
        if service_input and isinstance(service_input, Tag):
            self._current_service = str(service_input.get("value", ""))

        rc_input = soup.find("input", {"name": "requestCount"})
        if rc_input and isinstance(rc_input, Tag):
            try:
                self._request_count = int(str(rc_input.get("value", "0")))
            except ValueError:
                self._request_count = 0

    def _collect_form_data(self, soup: BeautifulSoup) -> dict[str, str]:
        """Collect all form fields from the page (hidden inputs and selects).

        For select elements, uses the selected option or empty string if none selected.
        This matches browser behavior where unselected dropdowns send empty values.
        """
        form = soup.find("form")
        if not form or not isinstance(form, Tag):
            return {}

        data: dict[str, str] = {}

        for inp in form.find_all("input"):
            if not isinstance(inp, Tag):
                continue
            name = inp.get("name")
            itype = str(inp.get("type", "")).lower()
            if name and itype not in ("submit", "button", "image"):
                data[str(name)] = str(inp.get("value", ""))

        for sel in form.find_all("select"):
            if not isinstance(sel, Tag):
                continue
            name = sel.get("name")
            if name:
                selected = sel.find("option", selected=True)
                if selected and isinstance(selected, Tag):
                    data[str(name)] = str(selected.get("value", ""))
                else:
                    # No option selected - send empty string (browser default)
                    data[str(name)] = ""

        return data

    def _post_form(self, data: dict[str, str]) -> BeautifulSoup:
        """Submit form data and return parsed response.

        The requestCount field must match the value from the current page's
        hidden field - the server validates this to prevent duplicate submissions.
        """
        data["scriptEnabled"] = "true"
        # Do NOT increment requestCount - use the value already in the form data

        url = f"https://bsz.ibs-bw.de{self._current_action}"
        resp = self._client.post(url, data=data)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        self._current_soup = soup
        self._extract_session_info(soup)
        return soup

    def _navigate_link(self, link_id: str) -> BeautifulSoup:
        """Navigate using the htmlOnLink mechanism."""
        if not self._current_soup:
            raise RuntimeError("No current page loaded")

        data = self._collect_form_data(self._current_soup)
        # Mimic htmlOnLink: set selected = "ZTEXT       " + link_id
        data["selected"] = f"ZTEXT       {link_id}"
        data["keyCode"] = "0"

        return self._post_form(data)

    def _click_toolbar(self, toolbar_name: str) -> BeautifulSoup:
        """Click a toolbar button (for pagination etc)."""
        if not self._current_soup:
            raise RuntimeError("No current page loaded")

        data = self._collect_form_data(self._current_soup)
        # Remove any existing toolbar fields from data
        toolbar_keys = [k for k in data if k.startswith("$Toolbar")]
        for k in toolbar_keys:
            del data[k]

        # Add the clicked toolbar button coordinates
        data[f"{toolbar_name}.x"] = "1"
        data[f"{toolbar_name}.y"] = "1"

        return self._post_form(data)

    def _click_submit(self, button_name: str) -> BeautifulSoup:
        """Click a submit button."""
        if not self._current_soup:
            raise RuntimeError("No current page loaded")

        data = self._collect_form_data(self._current_soup)
        data[button_name] = "Suchen"

        return self._post_form(data)

    def _parse_results(self, soup: BeautifulSoup) -> SearchResponse:
        """Parse a search results page into a SearchResponse."""
        response = SearchResponse()

        # Extract query description and count
        page_text = soup.get_text()
        count_match = re.search(r'Treffer:\s*([\d.]+)', page_text)
        if count_match:
            response.total_results = int(count_match.group(1).replace(".", ""))

        query_match = re.search(
            r'Gesucht wurde mit "([^"]+)"', page_text
        )
        if query_match:
            response.query_description = query_match.group(1)

        scope_match = re.search(r'im "([^"]+)"', page_text)
        if scope_match:
            response.query_description += f' in "{scope_match.group(1)}"'

        # Parse result items
        result_items = soup.select(".rList li")
        for item in result_items:
            if not isinstance(item, Tag):
                continue
            result = self._parse_result_item(item)
            if result:
                response.current_page_results.append(result)

        # Check for pagination (disabled buttons have class "toolbar_img_dis")
        next_btn = soup.find("input", {"name": "$Toolbar_3", "type": "image"})
        prev_btn = soup.find("input", {"name": "$Toolbar_2", "type": "image"})
        response.has_next_page = (
            next_btn is not None
            and isinstance(next_btn, Tag)
            and not next_btn.get("disabled")
        )
        response.has_previous_page = (
            prev_btn is not None
            and isinstance(prev_btn, Tag)
            and not prev_btn.get("disabled")
        )

        self._on_results_page = True
        self._on_detail_page = False

        return response

    def _parse_result_item(self, item: Tag) -> Optional[SearchResult]:
        """Parse a single result list item.

        Uses the structured CSS grid layout where available:
        - .rList_num: position number
        - .rList_titel a: title link with htmlOnLink item ID
        - .rList_jahr: publication year
        - .rList_name: author/publisher
        - .rList_sig: call number/signature
        - .rList_medium img: media type icon
        - .rList_availability img: availability icon
        - .rList_cover img.img-delayed: cover image (data-src)
        """
        result = SearchResult()

        # Extract item ID and title from link
        link = item.find("a", href=re.compile(r"htmlOnLink"))
        if link and isinstance(link, Tag):
            href = str(link.get("href", ""))
            id_match = re.search(r"htmlOnLink\('([^']+)'\)", href)
            if id_match:
                result.item_id = id_match.group(1)
            result.title = link.get_text(strip=True)

        if not result.item_id or result.item_id.startswith("*"):
            return None

        # Position number from structured grid
        num_div = item.select_one(".rList_num")
        if num_div and isinstance(num_div, Tag):
            num_text = num_div.get_text(strip=True)
            if num_text.isdigit():
                result.position = int(num_text)

        # Year from structured grid
        year_div = item.select_one(".rList_jahr")
        if year_div and isinstance(year_div, Tag):
            result.year = year_div.get_text(strip=True)

        # Author/publisher from structured grid
        # The name div may contain a <br/> separating author from "In:" reference
        name_div = item.select_one(".rList_name")
        if name_div and isinstance(name_div, Tag):
            br = name_div.find("br")
            if br:
                # Split on <br/>: before = author, after = "In:" reference
                parts_before = []
                parts_after = []
                found_br = False
                for child in name_div.children:
                    if child == br or (isinstance(child, Tag) and child.name == "br"):
                        found_br = True
                        continue
                    text = child.get_text(strip=True) if isinstance(child, Tag) else str(child).strip()
                    if text:
                        if found_br:
                            parts_after.append(text)
                        else:
                            parts_before.append(text)
                result.author = " ".join(parts_before)
                contained = " ".join(parts_after)
                if contained.startswith("In:"):
                    result.contained_in = contained[3:].strip()
                elif contained:
                    result.contained_in = contained
            else:
                result.author = name_div.get_text(strip=True)

        # Signature from structured grid
        sig_div = item.select_one(".rList_sig")
        if sig_div and isinstance(sig_div, Tag):
            result.signature = sig_div.get_text(strip=True)

        # Media type from icon
        medium_div = item.select_one(".rList_medium img")
        if medium_div and isinstance(medium_div, Tag):
            result.media_type = str(medium_div.get("alt", ""))

        # Availability from icon
        avail_img = item.select_one(".rList_availability img")
        if avail_img and isinstance(avail_img, Tag):
            result.availability = str(avail_img.get("alt", ""))

        # Cover image URL (lazy-loaded via data-src)
        cover_img = item.select_one(".rList_cover img.img-delayed")
        if cover_img and isinstance(cover_img, Tag):
            cover_src = str(cover_img.get("data-src", ""))
            if cover_src:
                result.cover_url = cover_src

        # Fallback: full text for details
        result.details = item.get_text(separator=" | ", strip=True)

        return result

    def _parse_detail(self, soup: BeautifulSoup, item_id: str) -> ItemDetail:
        """Parse an item detail page.

        The detail page (Vollanzeige) has:
        - div#R27: title in an aDISListe
        - div#R06: metadata in table.gi elements (th=label, td=value)
        - div#R08: holdings in table.rTable_table (library, location, signature, etc.)
        - Zitierlink: stable permalink to the item
        """
        detail = ItemDetail(item_id=item_id)

        # Extract title from div#R27 or h2
        title_div = soup.select_one("#R27")
        if title_div and isinstance(title_div, Tag):
            detail.title = title_div.get_text(strip=True)
        else:
            h2_tags = soup.find_all("h2")
            for h2 in h2_tags:
                if isinstance(h2, Tag):
                    text = h2.get_text(strip=True)
                    if text and "Aktuelle Seite:" in text:
                        detail.title = text.replace("Aktuelle Seite:", "").strip()
                        break

        # Extract Zitierlink (citation/permanent link)
        # The link text is "Zitierlink" inside a td cell
        for a_tag in soup.find_all("a"):
            if isinstance(a_tag, Tag) and "Zitierlink" in a_tag.get_text():
                href = str(a_tag.get("href", ""))
                if href and "DirectLink" in href:
                    detail.link = href
                    break

        # Parse metadata from table.gi elements inside div#R06
        r06 = soup.select_one("#R06")
        metadata_tables = r06.select("table.gi") if r06 else soup.select("table.gi")

        for table in metadata_tables:
            if not isinstance(table, Tag):
                continue
            for row in table.find_all("tr"):
                if not isinstance(row, Tag):
                    continue
                th = row.find("th")
                td = row.find("td")
                if th and td and isinstance(th, Tag) and isinstance(td, Tag):
                    label = th.get_text(strip=True)
                    # For values, preserve line breaks as separators
                    # Links in td may contain structured data
                    value_parts = []
                    for br in td.find_all("br"):
                        br.replace_with(" ; ")
                    value = td.get_text(strip=True)

                    if not label or not value:
                        continue
                    if label == "Zitierlink":
                        continue  # already handled

                    # Handle duplicate labels by appending
                    if label in detail.fields:
                        detail.fields[label] += f" ; {value}"
                    else:
                        detail.fields[label] = value

        # Parse holdings from div#R08 table.rTable_table
        r08 = soup.select_one("#R08")
        if r08 and isinstance(r08, Tag):
            holdings_table = r08.select_one("table.rTable_table")
            if holdings_table and isinstance(holdings_table, Tag):
                # Get column headers
                headers = []
                for th in holdings_table.select("thead th"):
                    if isinstance(th, Tag):
                        headers.append(th.get_text(strip=True))

                # Parse data rows
                for row in holdings_table.select("tbody tr"):
                    if not isinstance(row, Tag):
                        continue
                    cells = row.find_all("td")
                    if cells:
                        holding = {}
                        for i, cell in enumerate(cells):
                            if isinstance(cell, Tag):
                                key = headers[i] if i < len(headers) else f"col_{i}"
                                value = cell.get_text(strip=True)
                                if value:
                                    holding[key] = value
                        if holding:
                            detail.holdings.append(holding)

        # Extract external links from div#R16
        r16 = soup.select_one("#R16")
        if r16 and isinstance(r16, Tag):
            for ext_a in r16.find_all("a"):
                if isinstance(ext_a, Tag):
                    href = str(ext_a.get("href", ""))
                    text = ext_a.get_text(strip=True)
                    if href and text and href.startswith("http"):
                        detail.external_links.append({"text": text, "url": href})

        # Extract cover image
        cover_img = soup.select_one(".rList_cover img.img-delayed")
        if cover_img and isinstance(cover_img, Tag):
            cover_src = str(cover_img.get("data-src", ""))
            if cover_src:
                detail.cover_url = cover_src

        # If no Zitierlink found, try to construct one from K10Plus number
        if not detail.link or "SAKSWB" not in detail.link:
            k10plus = detail.fields.get("Nummer", "")
            # Extract the K10Plus number (before "(K10Plus-Nummer)")
            k10_match = re.search(r"([0-9A-Za-z]+)\s*\(K10Plus", k10plus)
            if k10_match:
                k10_id = k10_match.group(1)
                detail.link = (
                    f"https://bsz.ibs-bw.de/aDISWeb/app?"
                    f"service=direct/0/Home/$DirectLink&sp=SOPAC54"
                    f"&sp=SAKSWB-IdNr{k10_id}"
                )
            else:
                detail.link = (
                    f"https://bsz.ibs-bw.de/aDISWeb/app?"
                    f"service=direct/0/Home/$DirectLink&sp=SOPAC54"
                )

        self._on_detail_page = True
        self._on_results_page = False

        return detail

    # ---- Public API ----

    def search(self, query: str, scope: str = "all") -> SearchResponse:
        """Perform a simple (quick) search.

        Args:
            query: Search terms.
            scope: Search scope - "all", "library", or "interlibrary".

        Returns:
            SearchResponse with results.
        """
        self._ensure_session()

        # If not on home page, re-initialize
        if self._on_results_page or self._on_detail_page:
            self._init_session()

        if not self._current_soup:
            raise RuntimeError("Failed to load OPAC page")

        data = self._collect_form_data(self._current_soup)
        data["$Autosuggest"] = query
        data["textButton"] = "Suchen"

        # Set search scope
        scope_value = SEARCH_SCOPES.get(scope, SEARCH_SCOPES["all"])
        data["select"] = scope_value

        soup = self._post_form(data)

        # Check if we landed on the results page or the advanced search page
        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""

        if "Trefferliste" in title:
            return self._parse_results(soup)
        elif "Erweiterte Suche" in title:
            # The search redirected to advanced search - this happens with empty queries
            # Try submitting from the advanced search form
            return SearchResponse(
                query_description=f"Search for '{query}' returned no results or redirected to advanced search"
            )
        else:
            # Single result might go directly to detail
            return SearchResponse(
                query_description=f"Search for '{query}'",
                total_results=1,
            )

    def advanced_search(
        self,
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
    ) -> SearchResponse:
        """Perform an advanced search with multiple fields.

        Args:
            field1_category: Category for first search field (see SEARCH_CATEGORIES keys).
            field1_term: Search term for first field.
            field2_category: Category for second field (empty to skip).
            field2_term: Search term for second field.
            field2_operator: Boolean operator connecting field 1 and 2 ("and", "or", "not").
            field3_category: Category for third field.
            field3_term: Search term for third field.
            field3_operator: Boolean operator connecting to field 3.
            field4_category: Category for fourth field.
            field4_term: Search term for fourth field.
            field4_operator: Boolean operator connecting to field 4.
            media_type: Media type filter (see MEDIA_TYPES keys).
            language: Language filter (see LANGUAGES keys).
            publisher: Publisher name.
            place: Place of publication.
            year_exact: Exact year.
            year_from: Year range start.
            year_to: Year range end.
            scope: Search scope - "all", "library", or "interlibrary".
            new_acquisitions: Filter by recent acquisitions - "all", "1_week",
                "1_month", "2_months", or "4_months".
            availability: Filter by availability - "all" or "loanable".
            volume: Volume number (for journals/series).
            issue: Issue number (for journals).
            edition: Edition number.

        Returns:
            SearchResponse with results.
        """
        self._ensure_session()

        # Navigate to advanced search page first
        # We need to get to the advanced search form
        if self._on_results_page or self._on_detail_page:
            self._init_session()

        if not self._current_soup:
            raise RuntimeError("Failed to load OPAC page")

        # Submit the home page form to navigate to advanced search.
        # The "Erweiterte Suche" is a submit button. We pass it as a form field
        # to indicate it was the button that was clicked.
        data = self._collect_form_data(self._current_soup)
        # Only include the button that was clicked, not other submit buttons
        data["textButton$0"] = "Erweiterte Suche"

        soup = self._post_form(data)

        # Check we're on the advanced search page
        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""

        if "Erweiterte Suche" not in title:
            # Retry with a fresh session
            self._init_session()
            data = self._collect_form_data(self._current_soup)
            data["textButton$0"] = "Erweiterte Suche"
            soup = self._post_form(data)

        # Now fill in the advanced search form
        data = self._collect_form_data(soup)

        # Set search scope
        data["select"] = SEARCH_SCOPES.get(scope, SEARCH_SCOPES["all"])

        # Field 1
        cat1 = SEARCH_CATEGORIES.get(field1_category, field1_category)
        data["select$0"] = cat1
        data["$Autosuggest$0"] = field1_term

        # Field 2
        if field2_term and field2_category:
            cat2 = SEARCH_CATEGORIES.get(field2_category, field2_category)
            op2 = OPERATORS.get(field2_operator, "UND")
            data["select$1"] = op2
            data["select$2"] = cat2
            data["$Autosuggest$1"] = field2_term

        # Field 3
        if field3_term and field3_category:
            cat3 = SEARCH_CATEGORIES.get(field3_category, field3_category)
            op3 = OPERATORS.get(field3_operator, "UND")
            data["select$3"] = op3
            data["select$4"] = cat3
            data["$Autosuggest$2"] = field3_term

        # Field 4
        if field4_term and field4_category:
            cat4 = SEARCH_CATEGORIES.get(field4_category, field4_category)
            op4 = OPERATORS.get(field4_operator, "UND")
            data["select$5"] = op4
            data["select$6"] = cat4
            data["$Autosuggest$3"] = field4_term

        # Media type
        data["select$7"] = MEDIA_TYPES.get(media_type, MEDIA_TYPES["all"])

        # Language
        data["select$8"] = LANGUAGES.get(language, LANGUAGES["all"])

        # Additional fields
        if publisher:
            data["$Textfield"] = publisher
        if place:
            data["$Textfield$0"] = place
        if year_exact:
            data["$Textfield$1"] = year_exact
        if year_from:
            data["$Textfield$2"] = year_from
        if year_to:
            data["$Textfield$3"] = year_to

        # Volume, issue, edition
        if volume:
            data["$Textfield$4"] = volume
        if issue:
            data["$Textfield$5"] = issue
        if edition:
            data["$Textfield$6"] = edition

        # New acquisitions filter
        data["select$9"] = NEW_ACQUISITIONS.get(new_acquisitions, NEW_ACQUISITIONS["all"])

        # Availability filter
        data["select$10"] = AVAILABILITY.get(availability, AVAILABILITY["all"])

        # Submit the advanced search - use textButton$2 (the advanced search submit)
        data["textButton$2"] = "Suchen"

        soup = self._post_form(data)

        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""

        if "Trefferliste" in title:
            return self._parse_results(soup)
        else:
            # Check if there's an error or no results message
            page_text = soup.get_text()
            if "keine Treffer" in page_text.lower() or "0 Treffer" in page_text:
                return SearchResponse(
                    query_description="No results found",
                    total_results=0,
                )
            return SearchResponse(
                query_description=f"Advanced search completed - page: {title}",
                total_results=0,
            )

    def next_page(self) -> SearchResponse:
        """Navigate to the next page of results.

        Returns:
            SearchResponse with results from the next page.
        """
        if not self._on_results_page or not self._current_soup:
            raise RuntimeError("Not on a results page. Perform a search first.")

        soup = self._click_toolbar("$Toolbar_3")

        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""

        if "Trefferliste" in title:
            return self._parse_results(soup)
        return SearchResponse(query_description="Failed to navigate to next page")

    def previous_page(self) -> SearchResponse:
        """Navigate to the previous page of results.

        Returns:
            SearchResponse with results from the previous page.
        """
        if not self._on_results_page or not self._current_soup:
            raise RuntimeError("Not on a results page. Perform a search first.")

        soup = self._click_toolbar("$Toolbar_2")

        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""

        if "Trefferliste" in title:
            return self._parse_results(soup)
        return SearchResponse(query_description="Failed to navigate to previous page")

    def get_item_details(self, item_id: str) -> ItemDetail:
        """Get detailed metadata for a specific item.

        Args:
            item_id: The item identifier (e.g., "AK62937472").

        Returns:
            ItemDetail with metadata and holdings.
        """
        if not self._current_soup:
            raise RuntimeError("No session active. Perform a search first.")

        soup = self._navigate_link(item_id)

        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""

        detail = self._parse_detail(soup, item_id)
        detail.link = self._get_item_link(item_id)

        return detail

    def back_to_results(self) -> SearchResponse:
        """Navigate back to the results list from a detail page.

        Returns:
            SearchResponse with the current results page.
        """
        if not self._current_soup:
            raise RuntimeError("No session active.")

        # On the detail page, toolbar buttons are:
        # $Toolbar_0 = back to previous page
        # $Toolbar_5 = back to result list (zur Trefferliste)
        # Try $Toolbar_5 first (explicit "zur Trefferliste"), fall back to $Toolbar_0
        toolbar_name = "$Toolbar_5"
        btn = self._current_soup.find("input", {"name": toolbar_name, "type": "image"})
        if not btn:
            toolbar_name = "$Toolbar_0"

        soup = self._click_toolbar(toolbar_name)

        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""

        if "Trefferliste" in title:
            return self._parse_results(soup)
        return SearchResponse(query_description="Failed to navigate back to results")

    def sort_results(self, sort_by: str = "relevance") -> SearchResponse:
        """Sort the current search results.

        Args:
            sort_by: Sort option - "relevance", "title", "author",
                "year_desc", or "year_asc".

        Returns:
            SearchResponse with re-sorted results.
        """
        if not self._on_results_page or not self._current_soup:
            raise RuntimeError("Not on a results page. Perform a search first.")

        if sort_by not in SORT_OPTIONS:
            raise ValueError(
                f"Invalid sort option '{sort_by}'. "
                f"Use one of: {', '.join(SORT_OPTIONS.keys())}"
            )

        button_name, button_value = SORT_OPTIONS[sort_by]
        data = self._collect_form_data(self._current_soup)
        data[button_name] = button_value

        soup = self._post_form(data)

        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""

        if "Trefferliste" in title:
            return self._parse_results(soup)
        return SearchResponse(
            query_description=f"Sort by {sort_by} failed - page: {title}"
        )

    def export_results(self, fmt: str = "bibtex") -> str:
        """Export current search results in a citation format.

        Exports up to 300 titles from the current result set.

        Args:
            fmt: Export format - "bibtex", "citavi", "endnote", "procite",
                "refworks", "reference_manager", or "zotero".

        Returns:
            Citation data as a string in the requested format.
        """
        if not self._on_results_page or not self._current_soup:
            raise RuntimeError("Not on a results page. Perform a search first.")

        if fmt not in EXPORT_BUTTONS_RESULTS:
            raise ValueError(
                f"Invalid export format '{fmt}'. "
                f"Use one of: {', '.join(EXPORT_BUTTONS_RESULTS.keys())}"
            )

        button_name = EXPORT_BUTTONS_RESULTS[fmt]
        data = self._collect_form_data(self._current_soup)
        data[button_name] = EXPORT_FORMATS[fmt]

        url = f"https://bsz.ibs-bw.de{self._current_action}"
        data["scriptEnabled"] = "true"
        resp = self._client.post(url, data=data)
        resp.raise_for_status()

        # Check if we got a file download (text content) or HTML page
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            # Might still contain the export data in the page
            # Re-parse to stay on the results page
            soup = BeautifulSoup(resp.text, "lxml")
            self._current_soup = soup
            self._extract_session_info(soup)
            # Check if there's a pre/textarea with export data
            pre = soup.find("pre")
            if pre:
                return pre.get_text()
            textarea = soup.find("textarea")
            if textarea:
                return textarea.get_text()
            return resp.text
        else:
            # Got a file download - return the content
            # Need to re-fetch the results page to maintain state
            return resp.text

    def export_item(self, fmt: str = "bibtex") -> str:
        """Export the current detail item in a citation format.

        Args:
            fmt: Export format - "bibtex", "citavi", "endnote", "procite",
                "refworks", "reference_manager", or "zotero".

        Returns:
            Citation data as a string in the requested format.
        """
        if not self._on_detail_page or not self._current_soup:
            raise RuntimeError(
                "Not on a detail page. View item details first."
            )

        if fmt not in EXPORT_BUTTONS_DETAIL:
            raise ValueError(
                f"Invalid export format '{fmt}'. "
                f"Use one of: {', '.join(EXPORT_BUTTONS_DETAIL.keys())}"
            )

        button_name = EXPORT_BUTTONS_DETAIL[fmt]
        data = self._collect_form_data(self._current_soup)
        data[button_name] = EXPORT_FORMATS[fmt]

        url = f"https://bsz.ibs-bw.de{self._current_action}"
        data["scriptEnabled"] = "true"
        resp = self._client.post(url, data=data)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            soup = BeautifulSoup(resp.text, "lxml")
            self._current_soup = soup
            self._extract_session_info(soup)
            pre = soup.find("pre")
            if pre:
                return pre.get_text()
            textarea = soup.find("textarea")
            if textarea:
                return textarea.get_text()
            return resp.text
        else:
            return resp.text

    def next_record(self) -> ItemDetail:
        """Navigate to the next record from the detail page.

        Moves to the next item in the result set without returning
        to the results list first.

        Returns:
            ItemDetail for the next record.
        """
        if not self._on_detail_page or not self._current_soup:
            raise RuntimeError(
                "Not on a detail page. View item details first."
            )

        next_btn = self._current_soup.find(
            "input", {"name": "$Toolbar_3", "type": "image"}
        )
        if next_btn and isinstance(next_btn, Tag) and next_btn.get("disabled"):
            raise RuntimeError("Already at the last record.")

        soup = self._click_toolbar("$Toolbar_3")
        return self._parse_detail(soup, self._extract_current_item_id(soup))

    def previous_record(self) -> ItemDetail:
        """Navigate to the previous record from the detail page.

        Moves to the previous item in the result set without returning
        to the results list first.

        Returns:
            ItemDetail for the previous record.
        """
        if not self._on_detail_page or not self._current_soup:
            raise RuntimeError(
                "Not on a detail page. View item details first."
            )

        prev_btn = self._current_soup.find(
            "input", {"name": "$Toolbar_2", "type": "image"}
        )
        if prev_btn and isinstance(prev_btn, Tag) and prev_btn.get("disabled"):
            raise RuntimeError("Already at the first record.")

        soup = self._click_toolbar("$Toolbar_2")
        return self._parse_detail(soup, self._extract_current_item_id(soup))

    def _extract_current_item_id(self, soup: BeautifulSoup) -> str:
        """Extract the item ID from a detail page.

        Looks for the K10Plus number or item reference on the page.
        """
        # Try to find from page text or metadata
        page_text = soup.get_text()
        # Look for item ID in the page title or header
        title_div = soup.select_one("#R27")
        if title_div:
            # Sometimes the item ID is in a link on the detail page
            for a_tag in title_div.find_all("a"):
                if isinstance(a_tag, Tag):
                    href = str(a_tag.get("href", ""))
                    id_match = re.search(r"htmlOnLink\('(AK[^']+)'\)", href)
                    if id_match:
                        return id_match.group(1)

        # Look for the Zitierlink to extract the ID
        for a_tag in soup.find_all("a"):
            if isinstance(a_tag, Tag) and "Zitierlink" in a_tag.get_text():
                href = str(a_tag.get("href", ""))
                id_match = re.search(r"SAKSWB-IdNr([0-9A-Za-z]+)", href)
                if id_match:
                    return f"AK{id_match.group(1)}"

        return "unknown"

    def _get_item_link(self, item_id: str) -> str:
        """Generate a shareable link to an item.

        Note: aDISWeb doesn't support stable deep links to items.
        This returns a link to start a search that should find the item.
        """
        return (
            f"https://bsz.ibs-bw.de/aDISWeb/app?"
            f"service=direct/0/Home/$DirectLink&sp=SOPAC54"
        )

    def get_search_link(self, query: str) -> str:
        """Get a link to the OPAC for manual searching.

        Args:
            query: Search terms to suggest.

        Returns:
            URL to the OPAC catalog.
        """
        return (
            f"https://bsz.ibs-bw.de/aDISWeb/app?"
            f"service=direct/0/Home/$DirectLink&sp=SOPAC54"
        )

    def get_available_categories(self) -> dict[str, str]:
        """Return available search categories."""
        return SEARCH_CATEGORIES.copy()

    def get_available_media_types(self) -> dict[str, str]:
        """Return available media types."""
        return MEDIA_TYPES.copy()

    def get_available_languages(self) -> dict[str, str]:
        """Return available languages."""
        return LANGUAGES.copy()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
