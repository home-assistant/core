"""Helper functions for the SIA integration."""
from datetime import timedelta
from typing import Tuple

from homeassistant.const import DEVICE_CLASS_TIMESTAMP

from .const import HUB_SENSOR_NAME, HUB_ZONE


def GET_ENTITY_AND_NAME(
    port: int, account: str, zone: int = 0, entity_type: str = None
) -> Tuple[str, str]:
    """Give back a entity_id and name according to the variables."""
    if zone == HUB_ZONE:
        entity_type_name = (
            "Last Heartbeat" if entity_type == DEVICE_CLASS_TIMESTAMP else "Power"
        )
        return (
            GET_ENTITY_ID(port, account, zone, entity_type),
            f"{port} - {account} - {entity_type_name}",
        )
    if entity_type:
        return (
            GET_ENTITY_ID(port, account, zone, entity_type),
            f"{port} - {account} - zone {zone} - {entity_type}",
        )
    return None


def GET_PING_INTERVAL(ping: int) -> timedelta:
    """Return the ping interval as timedelta."""
    return timedelta(minutes=ping)


def GET_ENTITY_ID(
    port: int, account: str, zone: int = 0, entity_type: str = None
) -> str:
    """Give back a entity_id according to the variables, defaults to the hub sensor entity_id."""
    if zone == HUB_ZONE:
        if entity_type == DEVICE_CLASS_TIMESTAMP:
            return f"{port}_{account}_{HUB_SENSOR_NAME}"
        return f"{port}_{account}_{entity_type}"
    if entity_type:
        return f"{port}_{account}_{zone}_{entity_type}"
    return None
