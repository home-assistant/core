"""DoorBird integration utils."""

from typing import Any, cast

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .device import ConfiguredDoorBird
from .models import DoorBirdConfigEntry


def get_mac_address_from_door_station_info(door_station_info: dict[str, Any]) -> str:
    """Get the mac address depending on the device type."""
    return door_station_info.get("PRIMARY_MAC_ADDR", door_station_info["WIFI_MAC_ADDR"])  # type: ignore[no-any-return]


def get_door_station_by_token(
    hass: HomeAssistant, token: str
) -> ConfiguredDoorBird | None:
    """Get door station by token."""
    for entry in async_get_entries(hass):
        door_station = entry.runtime_data.door_station
        if door_station.token == token:
            return door_station
    return None


@callback
def async_get_entries(hass: HomeAssistant) -> list[DoorBirdConfigEntry]:
    """Get all the doorbird entries."""
    entries = hass.config_entries.async_entries(
        DOMAIN, include_ignore=True, include_disabled=True
    )
    active_entries = [entry for entry in entries if hasattr(entry, "runtime_data")]
    return cast(list[DoorBirdConfigEntry], active_entries)
