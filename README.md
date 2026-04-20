# The SF Stack

Early scraping utilities for building an SF events aggregation pipeline.

## Project Structure

```
the-sf-stack/
├── schemas/              # Event schema definitions
│   ├── event.py         # StandardizedEvent base schema
│   └── sfgate.py        # SFGATE-specific schemas
├── scripts/              # Scraping scripts
│   └── scrape_sfgate.py # SFGATE/EVVNT scraper
└── data/                 # Scraped data output
```

All events are normalized to a `StandardizedEvent` schema defined in `schemas/event.py`. Source-specific fields are preserved in `source_metadata`. See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## SFGATE scraper

The first script targets SFGATE's `Things To Do` landing page and extracts the
embedded Next.js story cards as normalized JSON.

Run:

```bash
python3 scripts/scrape_sfgate.py --pretty
```

Write the scraped records to a file:

```bash
python3 scripts/scrape_sfgate.py --pretty --output data/sfgate-events.json
```

Filter down to a topic:

```bash
python3 scripts/scrape_sfgate.py --keyword concert --pretty
```

### Scrape EVVNT Events

Scrape the EVVNT-powered events feed behind SFGATE's event page:

```bash
# Scrape all events (featured + upcoming)
python3 scripts/scrape_sfgate.py \
  --mode featured-events \
  --event-types both \
  --pretty \
  --output data/sfgate-all-events.json

# Scrape only featured events
python3 scripts/scrape_sfgate.py \
  --mode featured-events \
  --event-types featured \
  --pretty \
  --output data/sfgate-featured-events.json

# Scrape only upcoming events
python3 scripts/scrape_sfgate.py \
  --mode featured-events \
  --event-types upcoming \
  --pretty \
  --output data/sfgate-upcoming-events.json
```

### Debug Mode

Inspect available API fields from the EVVNT API (useful for debugging):

```bash
python3 scripts/scrape_sfgate.py \
  --mode featured-events \
  --debug \
  --limit 1
```

This will print all available field names from the API response for the first event.

### Event Data Schema

All events use a standardized schema regardless of source:

**Core Fields** (present for all sources):
- `title` (string) - Event name
- `source` (string) - Source identifier (e.g., "sfgate")
- `source_url` (string) - Link to event page
- `start_time` (string) - ISO 8601 start time
- `end_time` (string|null) - ISO 8601 end time
- `venue` (string|null) - Venue name
- `location` (string|null) - City, country
- `category` (string|null) - Event category
- `description` (string|null) - Event description
- `organizer` (string|null) - Event organizer name
- `ticket_price` (string|null) - Ticket prices (e.g., "General: USD 20 | Student: USD 15")
- `is_free` (boolean|null) - Whether the event is free
- `source_metadata` (object|null) - Source-specific fields

**SFGATE Source Metadata:**
When `source` is "sfgate", the `source_metadata` object may include:
- `featured` (boolean) - Whether event is featured on SFGATE
- `event_id` (string) - EVVNT event ID
- `image_url` (string) - Event image URL
- `door_time` (string) - ISO 8601 door time
- `eventbrite_id` (string) - Eventbrite ID if available

**Example Output:**
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
  "ticket_price": "After Dark 18+: USD 22.95",
  "is_free": false,
  "source_metadata": {
    "featured": true,
    "event_id": "3559981",
    "image_url": "https://cdn.prod.discovery.evvnt.com/..."
  }
}
```

## Architecture

The scraper uses a **standardized schema** with **source-specific metadata** to support multiple event sources:

1. **StandardizedEvent** - Common schema used across all sources
2. **Source-Specific Records** - Internal representations (e.g., `SFGateEventRecord`)
3. **Normalization Layer** - Maps source records to standardized format
4. **Source Metadata** - Preserves source-specific fields without cluttering core schema

### Adding New Event Sources

To add a new event source:

1. Create a source-specific dataclass (e.g., `EventbriteEventRecord`)
2. Implement a scraping function that returns source-specific records
3. Create a normalization function: `normalize_to_standardized_event()`
4. Map core fields + put extras in `source_metadata`

**Example:**
```python
@dataclass
class EventbriteEventRecord:
    title: str
    # ... core fields ...
    # Eventbrite-specific fields
    eventbrite_id: str
    series_id: Optional[str]
    # ...

def normalize_eventbrite_to_standard(eb_event: EventbriteEventRecord) -> StandardizedEvent:
    return StandardizedEvent(
        # ... map core fields ...
        source_metadata={
            "eventbrite_id": eb_event.eventbrite_id,
            "series_id": eb_event.series_id,
        }
    )
```

This architecture makes it easy to:
- Query across all sources using core fields
- Preserve source-specific data for debugging/features
- Add new sources without breaking existing ones

### Notes

- The script currently scrapes editorial event/story cards from
  `https://www.sfgate.com/thingstodo/`, not every event listing on the site.
- In `featured-events` mode, the script reads SFGATE's embedded EVVNT widget
  config and fetches the underlying featured event feed directly.
- It uses browser-like headers because plain `curl` requests can trigger
  SFGATE's anti-bot challenge page.
- The output shape is designed to be a first-stage input for your later
  normalization, deduplication, and ranking pipeline.
