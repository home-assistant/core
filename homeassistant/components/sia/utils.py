"""Helper functions for the SIA integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pysiaalarm import SIAEvent

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityDescription,
)
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_CODE,
    ATTR_ID,
    ATTR_MESSAGE,
    ATTR_TIMESTAMP,
    ATTR_ZONE,
    SIA_NAME_FORMAT,
    SIA_NAME_FORMAT_HUB,
)

PING_INTERVAL_MARGIN = 30


@dataclass
class SIARequiredKeysMixin:
    """Mixin for required keys."""

    port: int
    account: str
    zone: int | None
    ping_interval: int
    code_consequences: dict[str, Any]


@dataclass
class SIAAlarmControlPanelEntityDescription(
    AlarmControlPanelEntityDescription,
    SIARequiredKeysMixin,
):
    """Describes SIA alarm control panel entity."""


@dataclass
class SIABinarySensorEntityDescription(
    BinarySensorEntityDescription,
    SIARequiredKeysMixin,
):
    """Describes SIA sensor entity."""


def get_name(port: int, account: str, zone: int | None, device_class: str) -> str:
    """Return the name of the zone."""
    if zone is None or zone == 0:
        return SIA_NAME_FORMAT_HUB.format(port, account, device_class)
    return SIA_NAME_FORMAT.format(port, account, zone, device_class)


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
        ATTR_TIMESTAMP: event.timestamp.isoformat()
        if event.timestamp
        else utcnow().isoformat(),
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
        "timestamp": event.timestamp.isoformat()
        if event.timestamp
        else utcnow().isoformat(),
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
