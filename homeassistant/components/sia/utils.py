"""Helper functions for the SIA integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from pysiaalarm import SIAEvent

from homeassistant.const import DEVICE_CLASS_TIMESTAMP

from .const import (
    EVENT_ACCOUNT,
    EVENT_CODE,
    EVENT_ID,
    EVENT_MESSAGE,
    EVENT_TIMESTAMP,
    EVENT_ZONE,
    HUB_SENSOR_NAME,
    HUB_ZONE,
    PING_INTERVAL_MARGIN,
)


def get_unavailability_interval(ping: int) -> float:
    """Return the interval to the next unavailability check."""
    return timedelta(minutes=ping, seconds=PING_INTERVAL_MARGIN).total_seconds()


def get_name(port: int, account: str, zone: int, entity_type: str) -> str:
    """Give back a entity_id and name according to the variables."""
    if zone == HUB_ZONE:
        return f"{port} - {account} - {'Last Heartbeat' if entity_type == DEVICE_CLASS_TIMESTAMP else 'Power'}"
    return f"{port} - {account} - zone {zone} - {entity_type}"


def get_entity_id(port: int, account: str, zone: int, entity_type: str) -> str:
    """Give back a entity_id according to the variables."""
    if zone == HUB_ZONE:
        return f"{port}_{account}_{HUB_SENSOR_NAME if entity_type == DEVICE_CLASS_TIMESTAMP else entity_type}"
    return f"{port}_{account}_{zone}_{entity_type}"


def get_unique_id(entry_id: str, account: str, zone: int, domain: str) -> str:
    """Return the unique id."""
    return f"{entry_id}_{account}_{zone}_{domain}"


def get_attr_from_sia_event(event: SIAEvent) -> dict[str, Any]:
    """Create the attributes dict from a SIAEvent."""
    return {
        EVENT_ACCOUNT: event.account,
        EVENT_ZONE: event.ri,
        EVENT_CODE: event.code,
        EVENT_MESSAGE: event.message,
        EVENT_ID: event.id,
        EVENT_TIMESTAMP: event.timestamp,
    }
