"""Helper functions for the SIA integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from pysiaalarm import SIAEvent

from .const import ATTR_CODE, ATTR_ID, ATTR_MESSAGE, ATTR_TIMESTAMP, ATTR_ZONE

PING_INTERVAL_MARGIN = 30


def get_unavailability_interval(ping: int) -> float:
    """Return the interval to the next unavailability check."""
    return timedelta(minutes=ping, seconds=PING_INTERVAL_MARGIN).total_seconds()


def get_attr_from_sia_event(event: SIAEvent) -> dict[str, Any]:
    """Create the attributes dict from a SIAEvent."""
    return {
        ATTR_ZONE: event.ri,
        ATTR_CODE: event.code,
        ATTR_MESSAGE: event.message,
        ATTR_ID: event.id,
        ATTR_TIMESTAMP: event.timestamp.isoformat(),
    }


def get_event_data_from_sia_event(event: SIAEvent) -> dict[str, Any]:
    """Create a dict from the SIA Event for the HA Event."""
    return {
        "message_type": event.message_type.value,
        "receiver": event.receiver,
        "line": event.line,
        "account": event.account,
        "sequence": event.sequence,
        "content": event.content,
        "ti": event.ti,
        "id": event.id,
        "ri": event.ri,
        "code": event.code,
        "message": event.message,
        "x_data": event.x_data,
        "timestamp": event.timestamp.isoformat(),
        "event_qualifier": event.event_qualifier,
        "event_type": event.event_type,
        "partition": event.partition,
        "extended_data": [
            {
                "identifier": xd.identifier,
                "name": xd.name,
                "description": xd.description,
                "length": xd.length,
                "characters": xd.characters,
                "value": xd.value,
            }
            for xd in event.extended_data
        ]
        if event.extended_data is not None
        else None,
        "sia_code": {
            "code": event.sia_code.code,
            "type": event.sia_code.type,
            "description": event.sia_code.description,
            "concerns": event.sia_code.concerns,
        }
        if event.sia_code is not None
        else None,
    }
