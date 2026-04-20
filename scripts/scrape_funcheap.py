#!/usr/bin/env python3
"""Scrape events from FunCheap's SF events calendar.

This scraper targets sf.funcheap.com/events/ and extracts event listings
from their HTML calendar page, normalizing to the StandardizedEvent schema.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests

# Add parent directory to sys.path to import schemas module
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import StandardizedEvent
from schemas.funcheap import FuncheapEventRecord, normalize_to_standardized_event


DEFAULT_URL = "https://sf.funcheap.com/events/"
SOURCE = "funcheap"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class ScrapeError(RuntimeError):
    """Raised when the scraper cannot extract the page data we need."""


def fetch_html(url: str, timeout: int) -> str:
    """Fetch HTML content from URL."""
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def text_or_none(value: Any) -> Optional[str]:
    """Convert value to stripped string or None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def html_decode(text: str) -> str:
    """Decode common HTML entities."""
    if not text:
        return text
    
    replacements = {
        '&#8217;': "'",
        '&#8220;': '"',
        '&#8221;': '"',
        '&#038;': '&',
        '&#8211;': '-',
        '&#8212;': '—',
        '&#150;': '-',
        '&quot;': '"',
        '&#039;': "'",
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
    }
    
    for entity, char in replacements.items():
        text = text.replace(entity, char)
    
    return text


def extract_post_id(element: str) -> Optional[str]:
    """Extract post ID from element."""
    match = re.search(r'id="post-(\d+)"', element)
    return match.group(1) if match else None


def extract_categories(element: str) -> List[str]:
    """Extract category names from class attribute."""
    match = re.search(r'class="([^"]+)"', element)
    if not match:
        return []
    
    classes = match.group(1).split()
    categories = []
    
    for cls in classes:
        if cls.startswith('category-'):
            category = cls.replace('category-', '').replace('-', ' ')
            categories.append(category)
    
    return categories


def extract_region(element: str) -> Optional[str]:
    """Extract region from class attribute."""
    match = re.search(r'region-([a-zA-Z-]+)', element)
    if match:
        region = match.group(1).replace('-', ' ').title()
        return region
    return None


def parse_featured_event(event_html: str, current_date: Optional[str]) -> Optional[FuncheapEventRecord]:
    """Parse a featured event (larger card format)."""
    post_id = extract_post_id(event_html)
    
    # Extract title and URL
    title_match = re.search(
        r'<div class="title entry-title"[^>]*>.*?<a href="([^"]+)"[^>]*title="([^"]+)"',
        event_html,
        re.DOTALL
    )
    if not title_match:
        return None
    
    source_url = text_or_none(title_match.group(1))
    title = text_or_none(html_decode(title_match.group(2)))
    
    if not title or not source_url:
        return None
    
    # Extract date/time from data attributes
    start_time = None
    end_time = None
    date_match = re.search(r'data-event-date="([^"]+)"', event_html)
    date_end_match = re.search(r'data-event-date-end="([^"]+)"', event_html)
    
    if date_match:
        # Format: "2026-04-19 11:00" -> ISO 8601
        date_str = date_match.group(1)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            start_time = dt.strftime("%Y-%m-%dT%H:%M:00-07:00")
        except ValueError:
            pass
    
    if date_end_match:
        date_str = date_end_match.group(1)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            end_time = dt.strftime("%Y-%m-%dT%H:%M:00-07:00")
        except ValueError:
            pass
    
    # Extract cost
    ticket_price = None
    is_free = None
    cost_match = re.search(r'<span class="cost">Cost:\s*([^<]+)</span>', event_html)
    if cost_match:
        price_str = text_or_none(cost_match.group(1))
        if price_str:
            ticket_price = price_str
            is_free = 'FREE' in price_str.upper()
    
    # Extract venue - appears after cost
    venue = None
    venue_match = re.search(r'<span class="cost">.*?</span>\s*\|\s*<span>([^<]+)</span>', event_html, re.DOTALL)
    if venue_match:
        venue = text_or_none(html_decode(venue_match.group(1)))
    
    # Extract description
    description = None
    desc_match = re.search(r'<p style="padding:0px;margin:0px;">([^<]+)', event_html)
    if desc_match:
        description = text_or_none(html_decode(desc_match.group(1)))
    
    # Extract categories and region
    categories = extract_categories(event_html)
    region = extract_region(event_html)
    is_top_pick = 'category-top-pick' in event_html
    
    # Use first category as main category
    category = categories[0] if categories else None
    
    return FuncheapEventRecord(
        title=title,
        source=SOURCE,
        source_url=source_url,
        start_time=start_time,
        end_time=end_time,
        venue=venue,
        location=region if region else None,
        category=category,
        description=description,
        organizer=None,
        ticket_price=ticket_price,
        is_free=is_free,
        post_id=post_id,
        is_top_pick=is_top_pick,
        price_note=None,
        categories=categories if categories else None,
        region=region,
    )


def parse_list_event(event_html: str, current_date: Optional[str]) -> Optional[FuncheapEventRecord]:
    """Parse a list event (table row format)."""
    post_id = extract_post_id(event_html)
    
    # Extract time from first td
    time_match = re.search(r'<td[^>]*>([^<]+)</td>', event_html)
    time_str = time_match.group(1).strip() if time_match else None
    
    # Extract title and URL from title2 span
    title_match = re.search(
        r'<span class="title2 entry-title">.*?<a href="([^"]+)"[^>]*title="([^"]+)"',
        event_html,
        re.DOTALL
    )
    if not title_match:
        return None
    
    source_url = text_or_none(title_match.group(1))
    title = text_or_none(html_decode(title_match.group(2)))
    
    if not title or not source_url:
        return None
    
    # Extract price from third td
    ticket_price = None
    is_free = None
    price_note = None
    
    # Try to find price with tooltip
    price_tooltip_match = re.search(
        r'<td>&nbsp;&nbsp;<a class="tt">([^<]+).*?<div class="middle">([^<]+)</div>',
        event_html,
        re.DOTALL
    )
    if price_tooltip_match:
        price_str = text_or_none(html_decode(price_tooltip_match.group(1)))
        tooltip_text = text_or_none(html_decode(price_tooltip_match.group(2)))
        if price_str:
            ticket_price = price_str
            is_free = 'FREE' in price_str.upper()
            price_note = tooltip_text
    else:
        # Try simple price format
        price_match = re.search(r'<td>&nbsp;&nbsp;([^<]+)</td>', event_html)
        if price_match:
            price_str = text_or_none(html_decode(price_match.group(1)))
            if price_str:
                ticket_price = price_str
                is_free = 'FREE' in price_str.upper()
    
    # Build start_time from current_date and time_str
    start_time = None
    if current_date and time_str:
        try:
            # Parse time like "6:00 pm" or "11:00 am"
            time_match = re.match(r'(\d{1,2}):(\d{2})\s*(am|pm)', time_str.lower())
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                ampm = time_match.group(3)
                
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                
                # Combine with current_date
                # current_date format: "Sunday, April 19, 2026"
                # Extract "April 19, 2026" part
                parts = current_date.split(',', 1)  # Split on first comma only
                if len(parts) > 1:
                    date_part = parts[1].strip()  # "April 19, 2026"
                    dt = datetime.strptime(f"{date_part} {hour:02d}:{minute:02d}", "%B %d, %Y %H:%M")
                    start_time = dt.strftime("%Y-%m-%dT%H:%M:00-07:00")
        except (ValueError, AttributeError):
            pass
    
    # Extract categories and region
    categories = extract_categories(event_html)
    region = extract_region(event_html)
    is_top_pick = 'category-top-pick' in event_html
    
    category = categories[0] if categories else None
    
    return FuncheapEventRecord(
        title=title,
        source=SOURCE,
        source_url=source_url,
        start_time=start_time,
        end_time=None,
        venue=None,
        location=region if region else None,
        category=category,
        description=None,
        organizer=None,
        ticket_price=ticket_price,
        is_free=is_free,
        post_id=post_id,
        is_top_pick=is_top_pick,
        price_note=price_note,
        categories=categories if categories else None,
        region=region,
    )


def extract_events(html: str, page_url: str) -> List[StandardizedEvent]:
    """Extract all events from FunCheap events page."""
    records: List[StandardizedEvent] = []
    seen_urls = set()
    
    # Split HTML into sections by date headings
    date_sections = re.split(r'<h2[^>]*>([^<]+)</h2>', html)
    
    current_date = None
    for i, section in enumerate(date_sections):
        # Even indices are content, odd indices are date headings
        if i % 2 == 1:
            # This is a date heading like "Sunday, April 19, 2026"
            current_date = section.strip()
            continue
        
        # Parse featured events (larger cards)
        featured_pattern = r'<div id="post-\d+"[^>]*class="left blog clearfloat[^"]*"[^>]*>(.*?)</div>\s*</td>'
        for match in re.finditer(featured_pattern, section, re.DOTALL):
            event_html = match.group(0)
            funcheap_record = parse_featured_event(event_html, current_date)
            
            if funcheap_record and funcheap_record.source_url not in seen_urls:
                seen_urls.add(funcheap_record.source_url)
                standardized_record = normalize_to_standardized_event(funcheap_record)
                records.append(standardized_record)
        
        # Parse list events (table rows)
        list_pattern = r'<tr id="post-\d+"[^>]*>(.*?)</tr>'
        for match in re.finditer(list_pattern, section, re.DOTALL):
            event_html = match.group(0)
            funcheap_record = parse_list_event(event_html, current_date)
            
            if funcheap_record and funcheap_record.source_url not in seen_urls:
                seen_urls.add(funcheap_record.source_url)
                standardized_record = normalize_to_standardized_event(funcheap_record)
                records.append(standardized_record)
    
    return records


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
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="Scrape FunCheap events into structured JSON."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Page to scrape.")
    parser.add_argument(
        "--keyword",
        help="Optional case-insensitive filter across title/description/category/venue/url.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of records to output.",
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
    return parser


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()
    
    try:
        html = fetch_html(args.url, args.timeout)
        records = extract_events(html, args.url)
        records = filter_event_records(records, args.keyword)
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
