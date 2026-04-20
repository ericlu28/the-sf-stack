#!/usr/bin/env python3
"""Scrape event-oriented stories from SFGATE's Things To Do section.

This is a pragmatic first ingestion script for The SF Stack. Instead of trying
to fully crawl SFGATE, it targets the public "Things To Do" landing page and
extracts the structured story cards embedded in Next.js page data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

# Add parent directory to sys.path to import schemas module
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import StandardizedEvent
from schemas.sfgate import SFGateEventRecord, normalize_to_standardized_event


DEFAULT_URL = "https://www.sfgate.com/thingstodo/"
SOURCE = "sfgate"
EVVNT_API_BASE = "https://discovery.evvnt.com/api"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


@dataclass
class StoryRecord:
    title: str
    source: str
    source_url: str
    section: Optional[str]
    collection: Optional[str]
    description: Optional[str]
    authors: List[str]
    published_at: Optional[str]
    image_url: Optional[str]
    scraped_from: str


class ScrapeError(RuntimeError):
    """Raised when the scraper cannot extract the page data we need."""


def fetch_html(url: str, timeout: int) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_next_data(html: str) -> Dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        raise ScrapeError("Could not find __NEXT_DATA__ on the page.")

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ScrapeError("Failed to decode __NEXT_DATA__ JSON.") from exc


def extract_evvnt_config(html: str) -> Tuple[str, int]:
    api_key_match = re.search(r'api_key:\s*"([^"]+)"', html)
    publisher_match = re.search(r"publisher_id:\s*(\d+)", html)
    if not api_key_match or not publisher_match:
        raise ScrapeError("Could not find EVVNT widget configuration on the page.")
    return api_key_match.group(1), int(publisher_match.group(1))


def text_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def get_collection_title(widget: Dict[str, Any]) -> Optional[str]:
    options = widget.get("options") or {}
    title = options.get("title")
    if isinstance(title, dict):
        return text_or_none(title.get("text"))
    return text_or_none(options.get("wcmCollectionTitle"))


def get_section_name(item: Dict[str, Any]) -> Optional[str]:
    for key in ("eyebrow", "section", "sectionName"):
        value = item.get(key)
        if isinstance(value, dict):
            for nested_key in ("text", "title", "name"):
                text = text_or_none(value.get(nested_key))
                if text:
                    return text
        text = text_or_none(value)
        if text:
            return text
    return None


def infer_section_from_url(source_url: str) -> Optional[str]:
    path = urlparse(source_url).path.strip("/")
    if not path:
        return None
    first_segment = path.split("/", 1)[0].strip()
    if not first_segment:
        return None
    return first_segment.replace("-", " ")


def build_location(event: Dict[str, Any]) -> Optional[str]:
    venue = event.get("venue") or {}
    town = text_or_none(venue.get("town"))
    country = text_or_none((event.get("country") or {}).get("name"))
    parts = [part for part in (town, country) if part]
    return ", ".join(parts) or None


def extract_numeric_price(price_str: str) -> Optional[float]:
    """Extract numeric price from formatted price string.
    
    Handles various formats:
    - "USD 22.95" -> 22.95
    - "General: USD 20 | Student: USD 15" -> 15.0 (minimum)
    - "Free: USD 0.0" -> 0.0
    
    Args:
        price_str: Formatted price string
        
    Returns:
        Numeric price value, or None if no valid number found
    """
    if not price_str:
        return None
    
    # Find all numeric values in the string (handles "USD 22.95", "$22.95", "22.95", etc.)
    import re
    pattern = r'(\d+\.?\d*)'
    matches = re.findall(pattern, price_str)
    
    if not matches:
        return None
    
    # Convert to floats
    prices = []
    for match in matches:
        try:
            prices.append(float(match))
        except ValueError:
            continue
    
    if not prices:
        return None
    
    # Return minimum price (lowest entry point)
    return min(prices)


def normalize_evvnt_event(
    event: Dict[str, Any], page_url: str, event_type: Optional[str] = None, debug: bool = False
) -> Optional[SFGateEventRecord]:
    title = text_or_none(event.get("title"))
    source_url = text_or_none(event.get("source_broadcast_url"))
    if not title or not source_url:
        return None

    venue = event.get("venue") or {}
    
    # Extract price information from the prices field
    prices_data = event.get("prices")
    ticket_price = None
    is_free = None
    
    if debug:
        print(f"\n=== Debug info for '{title}' ===", file=sys.stderr)
        print(f"All keys: {sorted(event.keys())}", file=sys.stderr)
        print(f"prices field type: {type(prices_data)}", file=sys.stderr)
        print(f"prices field value: {prices_data}", file=sys.stderr)
        print(f"=== End debug ===\n", file=sys.stderr)
    
    if prices_data:
        if isinstance(prices_data, dict):
            # prices is a dict like {'After Dark 18+': 'USD 22.95'}
            # Combine all ticket types and prices into a readable string
            price_parts = []
            all_free = True
            has_prices = False
            
            for ticket_type, price_value in prices_data.items():
                price_str = text_or_none(price_value)
                if price_str:
                    has_prices = True
                    # Format as "ticket_type: price"
                    price_parts.append(f"{ticket_type}: {price_str}")
                    # Check if this price indicates free
                    price_lower = price_str.lower()
                    if not any(indicator in price_lower for indicator in ["free", "$0", "0.0", "0.00", "no charge", "complimentary", "no cost"]):
                        all_free = False
            
            if price_parts:
                ticket_price = " | ".join(price_parts)
                is_free = all_free if has_prices else None
        elif isinstance(prices_data, str):
            ticket_price = text_or_none(prices_data)
        elif isinstance(prices_data, list) and prices_data:
            # If it's a list, take the first item
            first_price = prices_data[0]
            if isinstance(first_price, dict):
                ticket_price = (
                    text_or_none(first_price.get("description"))
                    or text_or_none(first_price.get("text"))
                    or text_or_none(first_price.get("price"))
                )
            elif isinstance(first_price, str):
                ticket_price = text_or_none(first_price)
    
    # If we have price text but haven't determined if it's free, analyze the text
    if ticket_price and is_free is None:
        price_lower = ticket_price.lower()
        is_free = any(indicator in price_lower for indicator in ["free", "$0", "0.0", "0.00", "no charge", "complimentary", "no cost"])
    
    # Extract image URL from EVVNT images array
    images = event.get("images") or []
    first_image = images[0] if images else {}
    image_url = (
        text_or_none(((first_image.get("featured_webp") or {}).get("url")))
        or text_or_none(((first_image.get("featured") or {}).get("url")))
        or text_or_none(((first_image.get("hero_webp") or {}).get("url")))
        or text_or_none(((first_image.get("hero") or {}).get("url")))
        or text_or_none(((first_image.get("original") or {}).get("url")))
    )
    
    return SFGateEventRecord(
        title=title,
        source=SOURCE,
        source_url=source_url,
        category=text_or_none(event.get("category_name")),
        description=text_or_none(event.get("summary")) or text_or_none(event.get("description")),
        venue=text_or_none(venue.get("name")),
        location=build_location(event),
        start_time=text_or_none(event.get("start_time")),
        end_time=text_or_none(event.get("end_time")),
        organizer=text_or_none(event.get("organiser_name")),
        ticket_price=ticket_price,
        is_free=is_free,
        # SFGATE/EVVNT specific fields
        featured=event_type == "featured" if event_type else None,
        event_id=str(event.get("source_id")) if event.get("source_id") is not None else None,
        image_url=image_url,
        door_time=text_or_none(event.get("door_time")),
        eventbrite_id=text_or_none(event.get("eventbrite_id")),
    )


def fetch_evvnt_home_page_events(
    api_key: str, publisher_id: int, timeout: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fetch events from EVVNT API.
    
    Returns:
        Tuple of (featured_events, upcoming_events)
    """
    response = requests.get(
        f"{EVVNT_API_BASE}/publisher/{publisher_id}/home_page_events",
        params={"api_key": api_key},
        headers=DEFAULT_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return (
        payload.get("rawFeaturedEvents") or [],
        payload.get("rawEvents") or [],
    )


def extract_featured_events(
    page_url: str, timeout: int, event_types: str = "both", debug: bool = False
) -> List[StandardizedEvent]:
    """Extract events from SFGATE Things To Do page.
    
    Args:
        page_url: URL to scrape
        timeout: HTTP timeout in seconds
        event_types: Which events to include - "featured", "upcoming", or "both"
        debug: If True, print debug info for first event
    
    Returns:
        List of StandardizedEvent objects
    """
    html = fetch_html(page_url, timeout)
    api_key, publisher_id = extract_evvnt_config(html)
    featured_events, upcoming_events = fetch_evvnt_home_page_events(
        api_key, publisher_id, timeout
    )
    
    records: List[StandardizedEvent] = []
    seen_urls = set()
    debug_shown = False

    # Process featured events
    if event_types in ("featured", "both"):
        for event in featured_events:
            if not isinstance(event, dict):
                continue
            show_debug = debug and not debug_shown
            sfgate_record = normalize_evvnt_event(event, page_url, event_type="featured", debug=show_debug)
            if show_debug:
                debug_shown = True
            if not sfgate_record or sfgate_record.source_url in seen_urls:
                continue
            seen_urls.add(sfgate_record.source_url)
            # Normalize to standardized format before adding
            standardized_record = normalize_to_standardized_event(sfgate_record)
            records.append(standardized_record)

    # Process upcoming events
    if event_types in ("upcoming", "both"):
        for event in upcoming_events:
            if not isinstance(event, dict):
                continue
            show_debug = debug and not debug_shown
            sfgate_record = normalize_evvnt_event(event, page_url, event_type="upcoming", debug=show_debug)
            if show_debug:
                debug_shown = True
            if not sfgate_record or sfgate_record.source_url in seen_urls:
                continue
            seen_urls.add(sfgate_record.source_url)
            # Normalize to standardized format before adding
            standardized_record = normalize_to_standardized_event(sfgate_record)
            records.append(standardized_record)

    return records


def normalize_item(item: Dict[str, Any], collection: Optional[str], page_url: str) -> Optional[StoryRecord]:
    title = text_or_none(item.get("title"))
    relative_url = text_or_none(item.get("url"))
    if not title or not relative_url:
        return None

    authors = []
    for author in item.get("authors") or []:
        name = text_or_none((author or {}).get("name"))
        if name:
            authors.append(name)

    description = (
        text_or_none(item.get("plainTextAbstract"))
        or text_or_none(item.get("abstract"))
        or text_or_none(item.get("excerpt"))
    )
    image = item.get("image") or {}
    image_url = (
        text_or_none(image.get("url"))
        or text_or_none(image.get("defaultUrl"))
        or text_or_none(image.get("originUrl"))
    )
    published_at = (
        text_or_none(item.get("displayedDate"))
        or text_or_none(item.get("lastModifiedDate"))
    )

    source_url = urljoin(page_url, relative_url)
    section = get_section_name(item) or infer_section_from_url(source_url)

    return StoryRecord(
        title=title,
        source=SOURCE,
        source_url=source_url,
        section=section,
        collection=collection,
        description=description,
        authors=authors,
        published_at=published_at,
        image_url=image_url,
        scraped_from=page_url,
    )


def extract_records(next_data: Dict[str, Any], page_url: str) -> List[StoryRecord]:
    page = (((next_data.get("props") or {}).get("pageProps") or {}).get("page") or {})
    zone_sets = page.get("zoneSets") or []
    records: List[StoryRecord] = []
    seen_urls = set()

    for zone_set in zone_sets:
        for zone in zone_set.get("zones") or []:
            for widget in zone.get("widgets") or []:
                collection = get_collection_title(widget)
                for item in widget.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    record = normalize_item(item, collection, page_url)
                    if not record or record.source_url in seen_urls:
                        continue
                    seen_urls.add(record.source_url)
                    records.append(record)

    return records


def filter_records(records: Iterable[StoryRecord], keyword: Optional[str]) -> List[StoryRecord]:
    if not keyword:
        return list(records)

    needle = keyword.lower()
    filtered: List[StoryRecord] = []
    for record in records:
        haystacks = [
            record.title,
            record.description or "",
            record.section or "",
            record.collection or "",
            record.source_url,
        ]
        if any(needle in value.lower() for value in haystacks):
            filtered.append(record)
    return filtered


def filter_event_records(records: Iterable[StandardizedEvent], keyword: Optional[str]) -> List[StandardizedEvent]:
    """Filter standardized event records by keyword."""
    if not keyword:
        return list(records)

    needle = keyword.lower()
    filtered: List[StandardizedEvent] = []
    for record in records:
        haystacks = [
            record.title,
            record.category or "",
            record.description or "",
            record.venue or "",
            record.location or "",
            record.source_url,
        ]
        if any(needle in value.lower() for value in haystacks):
            filtered.append(record)
    return filtered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape SFGATE's Things To Do stories into structured JSON."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Page to scrape.")
    parser.add_argument(
        "--keyword",
        help="Optional case-insensitive filter across title/description/section/url.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of records to print.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the JSON payload to disk.",
    )
    parser.add_argument(
        "--mode",
        choices=("stories", "featured-events"),
        default="stories",
        help="Choose whether to scrape SFGATE editorial stories or EVVNT featured events.",
    )
    parser.add_argument(
        "--event-types",
        choices=("featured", "upcoming", "both"),
        default="both",
        help="When mode is 'featured-events', which event types to include (default: both).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug information about available API fields (for first event).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.mode == "featured-events":
            records = extract_featured_events(args.url, args.timeout, args.event_types, args.debug)
            records = filter_event_records(records, args.keyword)
        else:
            html = fetch_html(args.url, args.timeout)
            next_data = extract_next_data(html)
            records = extract_records(next_data, args.url)
            records = filter_records(records, args.keyword)
    except (requests.RequestException, ScrapeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = [asdict(record) for record in records[: max(args.limit, 0)]]
    json_text = (
        json.dumps(payload, indent=2, ensure_ascii=False)
        if args.pretty
        else json.dumps(payload, ensure_ascii=False)
    )

    if args.output:
        output_dir = os.path.dirname(os.path.abspath(args.output))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as file:
            file.write(json_text)
            file.write("\n")
    else:
        print(json_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
