"""Event schemas for The SF Stack aggregation pipeline.

This package contains:
- StandardizedEvent: Core schema used across all sources
- Source-specific schemas: e.g., SFGateEventRecord
- Normalization functions: Convert source records to StandardizedEvent

Usage:
    from schemas import StandardizedEvent
    from schemas.sfgate import SFGateEventRecord, normalize_to_standardized_event
"""

from schemas.event import StandardizedEvent

__all__ = ["StandardizedEvent"]
