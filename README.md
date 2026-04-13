# The SF Stack

Early scraping utilities for building an SF events aggregation pipeline.

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

Scrape the EVVNT-powered featured events feed behind SFGATE's event page:

```bash
python3 scripts/scrape_sfgate.py \
  --mode featured-events \
  --url 'https://www.sfgate.com/thingstodo/?_evDiscoveryPath=/' \
  --pretty \
  --output data/sfgate-featured-events.json
```

Notes:

- The script currently scrapes editorial event/story cards from
  `https://www.sfgate.com/thingstodo/`, not every event listing on the site.
- In `featured-events` mode, the script reads SFGATE's embedded EVVNT widget
  config and fetches the underlying featured event feed directly.
- It uses browser-like headers because plain `curl` requests can trigger
  SFGATE's anti-bot challenge page.
- The output shape is designed to be a first-stage input for your later
  normalization, deduplication, and ranking pipeline.
