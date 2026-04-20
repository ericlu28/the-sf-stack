"""Event schemas for The SF Stack aggregation pipeline.

This package contains:
- StandardizedEvent: Core schema used across all sources
- Source-specific schemas: e.g., SFGateEventRecord, FuncheapEventRecord
- Normalization functions: Convert source records to StandardizedEvent

Usage:
    from schemas import StandardizedEvent
    from schemas.sfgate import SFGateEventRecord, normalize_to_standardized_event
    from schemas.funcheap import FuncheapEventRecord, normalize_to_standardized_event
"""

from schemas.event import StandardizedEvent, BaseEventRecord

__all__ = ["StandardizedEvent", "BaseEventRecord"]
