"""DoorBird integration utils."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .device import ConfiguredDoorBird
from .models import DoorBirdData


def get_mac_address_from_door_station_info(door_station_info: dict[str, Any]) -> str:
    """Get the mac address depending on the device type."""
    return door_station_info.get("PRIMARY_MAC_ADDR", door_station_info["WIFI_MAC_ADDR"])  # type: ignore[no-any-return]


def get_door_station_by_token(
    hass: HomeAssistant, token: str
) -> ConfiguredDoorBird | None:
    """Get door station by token."""
    domain_data: dict[str, DoorBirdData] = hass.data[DOMAIN]
    for data in domain_data.values():
        door_station = data.door_station
        if door_station.token == token:
            return door_station
    return None
