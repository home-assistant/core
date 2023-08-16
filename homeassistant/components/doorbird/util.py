"""DoorBird integration utils."""

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .device import ConfiguredDoorBird
from .models import DoorBirdData


def get_mac_address_from_door_station_info(door_station_info):
    """Get the mac address depending on the device type."""
    return door_station_info.get("PRIMARY_MAC_ADDR", door_station_info["WIFI_MAC_ADDR"])


def get_door_station_by_token(
    hass: HomeAssistant, token: str
) -> ConfiguredDoorBird | None:
    """Get door station by token."""
    return _get_door_station_by_attr(hass, "token", token)


def get_door_station_by_slug(
    hass: HomeAssistant, slug: str
) -> ConfiguredDoorBird | None:
    """Get door station by slug."""
    return _get_door_station_by_attr(hass, "slug", slug)


def _get_door_station_by_attr(
    hass: HomeAssistant, attr: str, val: str
) -> ConfiguredDoorBird | None:
    domain_data: dict[str, DoorBirdData] = hass.data[DOMAIN]
    for data in domain_data.values():
        door_station = data.door_station
        if getattr(door_station, attr) == val:
            return door_station
    return None


def get_all_door_stations(hass: HomeAssistant) -> list[ConfiguredDoorBird]:
    """Get all door stations."""
    domain_data: dict[str, DoorBirdData] = hass.data[DOMAIN]
    return [data.door_station for data in domain_data.values()]
