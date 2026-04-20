"""FunCheap-specific event schemas.

This module defines FunCheap-specific event representations and normalization logic.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from schemas.event import StandardizedEvent, BaseEventRecord


@dataclass
class FuncheapEventRecord(BaseEventRecord):
    """FunCheap-specific event record.
    
    This is the internal representation used during FunCheap scraping.
    Gets normalized to StandardizedEvent before output.
    
    Inherits core fields from BaseEventRecord, plus FunCheap-specific fields:
        post_id: FunCheap post ID
        is_top_pick: Whether event is marked as Editor's Top Pick
        price_note: Additional price details from tooltip
        categories: List of event categories
        region: Geographic region classification
    """
    # FunCheap specific fields
    post_id: Optional[str]
    is_top_pick: Optional[bool]
    price_note: Optional[str]
    categories: Optional[list]
    region: Optional[str]


def normalize_to_standardized_event(funcheap_event: FuncheapEventRecord) -> StandardizedEvent:
    """Convert FunCheap-specific event record to standardized event format.
    
    This is the normalization layer that maps source-specific data to the
    standardized schema used across all event sources. FunCheap-specific fields
    are preserved in the source_metadata dictionary.
    
    Args:
        funcheap_event: FunCheap-specific event record
        
    Returns:
        StandardizedEvent with FunCheap-specific fields in source_metadata
        
    Example:
        >>> funcheap_event = FuncheapEventRecord(
        ...     title="Comedy Night",
        ...     source="funcheap",
        ...     is_top_pick=True,
        ...     post_id="123456",
        ...     # ... other fields ...
        ... )
        >>> std_event = normalize_to_standardized_event(funcheap_event)
        >>> std_event.source_metadata
        {"is_top_pick": True, "post_id": "123456"}
    """
    # Build source_metadata with all FunCheap specific fields
    source_metadata: Dict[str, Any] = {}
    
    if funcheap_event.post_id:
        source_metadata["post_id"] = funcheap_event.post_id
    if funcheap_event.is_top_pick is not None:
        source_metadata["is_top_pick"] = funcheap_event.is_top_pick
    if funcheap_event.price_note:
        source_metadata["price_note"] = funcheap_event.price_note
    if funcheap_event.categories:
        source_metadata["categories"] = funcheap_event.categories
    if funcheap_event.region:
        source_metadata["region"] = funcheap_event.region
    
    return StandardizedEvent(
        title=funcheap_event.title,
        source=funcheap_event.source,
        source_url=funcheap_event.source_url,
        start_time=funcheap_event.start_time,
        end_time=funcheap_event.end_time,
        venue=funcheap_event.venue,
        location=funcheap_event.location,
        category=funcheap_event.category,
        description=funcheap_event.description,
        organizer=funcheap_event.organizer,
        ticket_price=funcheap_event.ticket_price,
        is_free=funcheap_event.is_free,
        source_metadata=source_metadata if source_metadata else None,
    )
