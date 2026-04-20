"""SFGATE/EVVNT-specific event schemas.

This module defines SFGATE-specific event representations and normalization logic.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from schemas.event import StandardizedEvent


@dataclass
class SFGateEventRecord:
    """SFGATE/EVVNT-specific event record.
    
    This is the internal representation used during SFGATE scraping.
    Gets normalized to StandardizedEvent before output.
    
    Core fields match StandardizedEvent, plus SFGATE-specific fields:
        event_id: EVVNT event source ID
        image_url: Event image URL from EVVNT
        door_time: Door opening time in ISO 8601 format
        eventbrite_id: Eventbrite ID if event is also on Eventbrite
        featured: Whether event is featured on SFGATE
    """
    # Core fields (match StandardizedEvent)
    title: str
    source: str
    source_url: str
    category: Optional[str]
    description: Optional[str]
    venue: Optional[str]
    location: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    organizer: Optional[str]
    ticket_price: Optional[str]
    is_free: Optional[bool]
    
    # SFGATE/EVVNT specific fields
    featured: Optional[bool]
    event_id: Optional[str]
    image_url: Optional[str]
    door_time: Optional[str]
    eventbrite_id: Optional[str]


def normalize_to_standardized_event(sfgate_event: SFGateEventRecord) -> StandardizedEvent:
    """Convert SFGATE-specific event record to standardized event format.
    
    This is the normalization layer that maps source-specific data to the
    standardized schema used across all event sources. SFGATE-specific fields
    are preserved in the source_metadata dictionary.
    
    Args:
        sfgate_event: SFGATE-specific event record
        
    Returns:
        StandardizedEvent with SFGATE-specific fields in source_metadata
        
    Example:
        >>> sfgate_event = SFGateEventRecord(
        ...     title="Concert",
        ...     source="sfgate",
        ...     featured=True,
        ...     event_id="123",
        ...     # ... other fields ...
        ... )
        >>> std_event = normalize_to_standardized_event(sfgate_event)
        >>> std_event.source_metadata
        {"featured": True, "event_id": "123"}
    """
    # Build source_metadata with all SFGATE/EVVNT specific fields
    source_metadata: Dict[str, Any] = {}
    
    if sfgate_event.featured is not None:
        source_metadata["featured"] = sfgate_event.featured
    if sfgate_event.event_id:
        source_metadata["event_id"] = sfgate_event.event_id
    if sfgate_event.image_url:
        source_metadata["image_url"] = sfgate_event.image_url
    if sfgate_event.door_time:
        source_metadata["door_time"] = sfgate_event.door_time
    if sfgate_event.eventbrite_id:
        source_metadata["eventbrite_id"] = sfgate_event.eventbrite_id
    
    return StandardizedEvent(
        title=sfgate_event.title,
        source=sfgate_event.source,
        source_url=sfgate_event.source_url,
        start_time=sfgate_event.start_time,
        end_time=sfgate_event.end_time,
        venue=sfgate_event.venue,
        location=sfgate_event.location,
        category=sfgate_event.category,
        description=sfgate_event.description,
        organizer=sfgate_event.organizer,
        ticket_price=sfgate_event.ticket_price,
        is_free=sfgate_event.is_free,
        source_metadata=source_metadata if source_metadata else None,
    )
