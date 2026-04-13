# The SF Stack

Early scraping utilities for building an SF events aggregation pipeline.

## SFGATE scraper

The first script targets SFGATE's `Things To Do` landing page and extracts the
embedded Next.js story cards as normalized JSON.

Run:

```bash
python3 scripts/scrape_sfgate.py --pretty
```

Filter down to a topic:

```bash
python3 scripts/scrape_sfgate.py --keyword concert --pretty
```

Notes:

- The script currently scrapes editorial event/story cards from
  `https://www.sfgate.com/thingstodo/`, not every event listing on the site.
- It uses browser-like headers because plain `curl` requests can trigger
  SFGATE's anti-bot challenge page.
- The output shape is designed to be a first-stage input for your later
  normalization, deduplication, and ranking pipeline.
