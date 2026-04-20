# The SF Stack - Architecture

## Overview

The SF Stack is an event aggregation pipeline designed to collect events from multiple sources into a unified, standardized format. The architecture prioritizes flexibility, extensibility, and data preservation.

## Project Structure

```
the-sf-stack/
├── schemas/                    # Event schema definitions
│   ├── __init__.py            # Package exports
│   ├── event.py               # StandardizedEvent base schema
│   └── sfgate.py              # SFGATE-specific schemas
├── scripts/                    # Scraping scripts
│   └── scrape_sfgate.py       # SFGATE/EVVNT scraper
├── data/                       # Scraped data output
├── ARCHITECTURE.md             # This file
└── README.md                   # Usage documentation
```

## Core Design Principles

### 1. Standardized Schema
All events, regardless of source, conform to a common `StandardizedEvent` schema with core fields that enable cross-source querying and deduplication.

### 2. Source-Specific Metadata
Each source can preserve unique fields in a `source_metadata` object, preventing data loss while keeping the core schema clean.

### 3. Normalization Layer
Each source implements a normalization function that maps from its internal representation to the standardized format.

## Data Schema

### StandardizedEvent

```python
@dataclass
class StandardizedEvent:
    """Standardized event schema used across all event sources."""
    title: str                              # Required
    source: str                             # Required (e.g., "sfgate")
    source_url: str                         # Required
    start_time: Optional[str]               # ISO 8601 format
    end_time: Optional[str]                 # ISO 8601 format
    venue: Optional[str]                    # Venue name
    location: Optional[str]                 # "City, Country"
    category: Optional[str]                 # Event category
    description: Optional[str]              # Event description
    organizer: Optional[str]                # Organizer name
    ticket_price: Optional[float]           # Numeric price (minimum if multiple tiers)
    is_free: Optional[bool]                 # Whether event is free
    source_metadata: Optional[Dict[str, Any]]  # Source-specific fields
```

### Example Output

```json
{
  "title": "After Dark: Climate Journeys",
  "source": "sfgate",
  "source_url": "https://www.sfgate.com/things-to-do/...",
  "start_time": "2026-04-23T18:00:00-07:00",
  "end_time": "2026-04-23T22:00:00-07:00",
  "venue": "Pier 15",
  "location": "San Francisco, United States",
  "category": "Museum",
  "description": "Climate change is a complex problem...",
  "organizer": "The Exploratorium",
  "ticket_price": 22.95,
  "is_free": false,
  "source_metadata": {
    "featured": true,
    "event_id": "3559981",
    "image_url": "https://cdn.prod.discovery.evvnt.com/...",
    "door_time": "2026-04-23T17:30:00-07:00",
    "ticket_price_formatted": "After Dark 18+: USD 22.95"
  }
}
```

## Source Implementation Pattern

### 1. Define Source-Specific Record

```python
@dataclass
class SFGateEventRecord:
    """SFGATE/EVVNT-specific event record."""
    # Core fields
    title: str
    source: str
    source_url: str
    # ... standard fields ...
    
    # Source-specific fields
    event_id: Optional[str]
    image_url: Optional[str]
    door_time: Optional[str]
    eventbrite_id: Optional[str]
```

### 2. Implement Scraping Function

```python
def extract_sfgate_events(url: str) -> List[SFGateEventRecord]:
    """Scrape events from SFGATE."""
    # Fetch and parse data
    # Return list of source-specific records
    pass
```

### 3. Create Normalization Function

```python
def normalize_to_standardized_event(
    sfgate_event: SFGateEventRecord
) -> StandardizedEvent:
    """Convert SFGATE record to standardized format."""
    
    # Build source metadata
    source_metadata = {}
    if sfgate_event.featured is not None:
        source_metadata["featured"] = sfgate_event.featured
    if sfgate_event.event_id:
        source_metadata["event_id"] = sfgate_event.event_id
    # ... add other source-specific fields ...
    
    # Return standardized event
    return StandardizedEvent(
        title=sfgate_event.title,
        source=sfgate_event.source,
        # ... map core fields ...
        source_metadata=source_metadata if source_metadata else None
    )
```

## Current Sources

### SFGATE (via EVVNT API)

**Source ID:** `"sfgate"`

**Internal Type:** `SFGateEventRecord`

**Source Metadata Fields:**
- `featured` (boolean) - Whether event is featured
- `event_id` (string) - EVVNT event ID
- `image_url` (string) - Event image URL
- `door_time` (string) - Door time in ISO 8601
- `eventbrite_id` (string) - Eventbrite ID if available

**Scraping Method:**
1. Fetches SFGATE's Things To Do page
2. Extracts EVVNT widget configuration
3. Calls EVVNT API directly for event data
4. Normalizes to StandardizedEvent format

## Adding New Sources

To add a new event source (e.g., Eventbrite, Meetup):

### 1. Create source schema file

Create `schemas/eventbrite.py`:

```python
"""Eventbrite-specific event schemas."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from schemas.event import StandardizedEvent


@dataclass
class EventbriteEventRecord:
    """Eventbrite-specific event record."""
    # Core fields
    title: str
    source: str
    source_url: str
    # ... other core fields ...
    
    # Eventbrite-specific fields
    eventbrite_id: str
    series_id: Optional[str]
    organizer_id: Optional[str]


def normalize_to_standardized_event(
    eb_event: EventbriteEventRecord
) -> StandardizedEvent:
    """Convert Eventbrite event to standardized format."""
    source_metadata = {
        "eventbrite_id": eb_event.eventbrite_id,
    }
    if eb_event.series_id:
        source_metadata["series_id"] = eb_event.series_id
    if eb_event.organizer_id:
        source_metadata["organizer_id"] = eb_event.organizer_id
    
    return StandardizedEvent(
        title=eb_event.title,
        source="eventbrite",
        source_url=eb_event.source_url,
        # ... map core fields ...
        source_metadata=source_metadata
    )
```

### 2. Create scraping script

Create `scripts/scrape_eventbrite.py`:

```python
#!/usr/bin/env python3
"""Scrape events from Eventbrite."""

import sys
from pathlib import Path

# Add parent directory to sys.path to import schemas
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import StandardizedEvent
from schemas.eventbrite import EventbriteEventRecord, normalize_to_standardized_event


def extract_eventbrite_events(api_key: str) -> List[StandardizedEvent]:
    """Scrape and normalize Eventbrite events."""
    # Fetch from Eventbrite API
    # Parse into EventbriteEventRecord objects
    # Normalize to StandardizedEvent
    pass
```

### 3. Import and use

Any script can now import both schemas:

```python
from schemas import StandardizedEvent
from schemas.eventbrite import EventbriteEventRecord
from schemas.sfgate import SFGateEventRecord
```

## Price Handling

### Numeric Price Extraction

The `ticket_price` field is a float for queryability and filtering:

**Price Extraction Rules:**
1. Extract all numeric values from price strings
2. For multiple price tiers (e.g., "General: USD 20 | Student: USD 15"), use **minimum** price
3. Free events have `ticket_price: 0.0` and `is_free: true`
4. Original formatted price string is preserved in `source_metadata.ticket_price_formatted`

**Examples:**
- `"USD 22.95"` → `22.95`
- `"General: USD 20 | Student: USD 15"` → `15.0` (minimum)
- `"Free: USD 0.0"` → `0.0`

**Benefits:**
- Sort events by price
- Filter by price range: `price < 20.0`
- Query free events: `is_free == true` or `price == 0.0`
- Still have original formatted text for display

## Benefits

### For Querying
- All events searchable by standard fields
- Easy filtering by venue, category, price, etc.
- Simple cross-source deduplication
- Numeric price enables sorting and range queries

### For Development
- Clear separation of concerns
- Easy to add new sources
- Source-specific data preserved for debugging
- No breaking changes when adding fields

### For Data Quality
- Validates core fields are present
- Maintains data lineage via source_metadata
- Preserves original source URLs for verification

## Future Enhancements

1. **Deduplication Pipeline**
   - Match events across sources by title, venue, start_time
   - Merge source_metadata from multiple sources
   - Rank canonical URLs

2. **Category Normalization**
   - Map source-specific categories to standard taxonomy
   - Enable better cross-source filtering

3. **Geocoding**
   - Convert location strings to lat/lon coordinates
   - Enable geographic queries

4. **Price Parsing**
   - Parse ticket_price strings into structured data
   - Support price range queries

5. **Embedding Generation**
   - Generate vector embeddings from title + description
   - Enable semantic search across events
