"""Standardized event schema for The SF Stack.

This module defines the core StandardizedEvent schema used across all event sources
in the aggregation pipeline. All source-specific events must normalize to this format.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class StandardizedEvent:
    """Standardized event schema used across all event sources.
    
    This is the normalized output format for The SF Stack event aggregator.
    All event sources must map their data to this schema.
    
    Attributes:
        title: Event name (required)
        source: Source identifier, e.g., "sfgate", "eventbrite" (required)
        source_url: Canonical URL to event page (required)
        start_time: Event start time in ISO 8601 format
        end_time: Event end time in ISO 8601 format
        venue: Venue name
        location: Location string, typically "City, Country"
        category: Event category/type
        description: Event description
        organizer: Name of event organizer
        ticket_price: Human-readable ticket price(s), e.g., "General: USD 20 | Student: USD 15"
        is_free: Whether the event is free to attend
        source_metadata: Dictionary containing source-specific fields that don't fit
                        in the core schema. This preserves data without cluttering
                        the standardized fields.
    
    Example:
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
    """
    title: str
    source: str
    source_url: str
    start_time: Optional[str]
    end_time: Optional[str]
    venue: Optional[str]
    location: Optional[str]
    category: Optional[str]
    description: Optional[str]
    organizer: Optional[str]
    ticket_price: Optional[str]
    is_free: Optional[bool]
    source_metadata: Optional[Dict[str, Any]]
