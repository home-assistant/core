"""Helper functions for the SIA integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pysiaalarm import SIAEvent
from pysiaalarm.utils import MessageTypes

from homeassistant.util.dt import utcnow

from .const import (
    ATTR_CODE,
    ATTR_ID,
    ATTR_MESSAGE,
    ATTR_TIMESTAMP,
    ATTR_ZONE,
    KEY_ALARM,
    SIA_HUB_ZONE,
)

PING_INTERVAL_MARGIN = 30


def get_unique_id_and_name(
    entry_id: str,
    port: int,
    account: str,
    zone: int,
    entity_key: str,
) -> tuple[str, str]:
    """Return the unique_id and name for an entity."""
    return (
        (
            f"{entry_id}_{account}_{zone}"
            if entity_key == KEY_ALARM
            else f"{entry_id}_{account}_{zone}_{entity_key}"
        ),
        (
            f"{port} - {account} - {entity_key}"
            if zone == SIA_HUB_ZONE
            else f"{port} - {account} - zone {zone} - {entity_key}"
        ),
    )


def get_unavailability_interval(ping: int) -> float:
    """Return the interval to the next unavailability check."""
    return timedelta(minutes=ping, seconds=PING_INTERVAL_MARGIN).total_seconds()


def get_attr_from_sia_event(event: SIAEvent) -> dict[str, Any]:
    """Create the attributes dict from a SIAEvent."""
    timestamp = event.timestamp if event.timestamp else utcnow()
    return {
        ATTR_ZONE: event.ri,
        ATTR_CODE: event.code,
        ATTR_MESSAGE: event.message,
        ATTR_ID: event.id,
        ATTR_TIMESTAMP: timestamp.isoformat()
        if isinstance(timestamp, datetime)
        else timestamp,
    }


def get_event_data_from_sia_event(event: SIAEvent) -> dict[str, Any]:
    """Create a dict from the SIA Event for the HA Event."""
    return {
        "message_type": event.message_type.value
        if isinstance(event.message_type, MessageTypes)
        else event.message_type,
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
        "timestamp": event.timestamp.isoformat()
        if isinstance(event.timestamp, datetime)
        else event.timestamp,
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
