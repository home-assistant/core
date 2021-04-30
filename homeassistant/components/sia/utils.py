"""Helper functions for the SIA integration."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

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
)


def get_id_and_name(
    port: int, account: str, zone: int = 0, entity_type: str = None
) -> tuple[str, str]:
    """Give back a entity_id and name according to the variables."""
    if zone == HUB_ZONE:
        entity_type_name = (
            "Last Heartbeat" if entity_type == DEVICE_CLASS_TIMESTAMP else "Power"
        )
        return (
            get_id(port, account, zone, entity_type),
            f"{port} - {account} - {entity_type_name}",
        )

    if not entity_type:
        raise ValueError("If zone is not 0, then a entity_type is required.")
    return (
        get_id(port, account, zone, entity_type),
        f"{port} - {account} - zone {zone} - {entity_type}",
    )


def get_ping_interval(ping: int) -> timedelta:
    """Return the ping interval as timedelta."""
    return timedelta(minutes=ping)


def get_id(port: int, account: str, zone: int, entity_type: str) -> str:
    """Give back a unique_id according to the variables, defaults to the hub sensor entity_id."""
    if zone == HUB_ZONE:
        if entity_type == DEVICE_CLASS_TIMESTAMP:
            return f"{port}_{account}_{HUB_SENSOR_NAME}"
        return f"{port}_{account}_{entity_type}"
    return f"{port}_{account}_{zone}_{entity_type}"


def get_attr_from_sia_event(event: SIAEvent) -> Mapping[str, str]:
    """Create the attributes dict from a SIAEvent."""
    return {
        EVENT_ACCOUNT: event.account,
        EVENT_ZONE: event.ri,
        EVENT_CODE: event.code,
        EVENT_MESSAGE: event.message,
        EVENT_ID: event.id,
        EVENT_TIMESTAMP: event.timestamp,
    }
