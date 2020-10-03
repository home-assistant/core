"""DoorBird integration utils."""

from .const import DOMAIN, DOOR_STATION


def get_mac_address_from_doorstation_info(doorstation_info):
    """Get the mac address depending on the device type."""
    if "PRIMARY_MAC_ADDR" in doorstation_info:
        return doorstation_info["PRIMARY_MAC_ADDR"]
    return doorstation_info["WIFI_MAC_ADDR"]


def get_doorstation_by_token(hass, token):
    """Get doorstation by token."""
    for config_entry_id in hass.data[DOMAIN]:
        doorstation = hass.data[DOMAIN][config_entry_id][DOOR_STATION]

        if token == doorstation.token:
            return doorstation


def get_doorstation_by_slug(hass, slug):
    """Get doorstation by slug."""
    for config_entry_id in hass.data[DOMAIN]:
        doorstation = hass.data[DOMAIN][config_entry_id][DOOR_STATION]

        if slug == doorstation.slug:
            return doorstation


def get_all_doorstations(hass):
    """Get all doorstations."""

    doorstations = []
    for config_entry_id in hass.data[DOMAIN]:
        if DOOR_STATION not in hass.data[DOMAIN][config_entry_id]:
            continue

        doorstation = hass.data[DOMAIN][config_entry_id][DOOR_STATION]
        doorstations.append(doorstation)

    return doorstations
