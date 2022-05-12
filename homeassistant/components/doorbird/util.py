"""DoorBird integration utils."""

from .const import DOMAIN, DOOR_STATION


def get_mac_address_from_doorstation_info(doorstation_info):
    """Get the mac address depending on the device type."""
    if "PRIMARY_MAC_ADDR" in doorstation_info:
        return doorstation_info["PRIMARY_MAC_ADDR"]
    return doorstation_info["WIFI_MAC_ADDR"]


def get_doorstation_by_token(hass, token):
    """Get doorstation by token."""
    return _get_doorstation_by_attr(hass, "token", token)


def get_doorstation_by_slug(hass, slug):
    """Get doorstation by slug."""
    return _get_doorstation_by_attr(hass, "slug", slug)


def _get_doorstation_by_attr(hass, attr, val):
    for entry in hass.data[DOMAIN].values():
        if DOOR_STATION not in entry:
            continue

        doorstation = entry[DOOR_STATION]

        if getattr(doorstation, attr) == val:
            return doorstation

    return None


def get_all_doorstations(hass):
    """Get all doorstations."""
    return [
        entry[DOOR_STATION]
        for entry in hass.data[DOMAIN].values()
        if DOOR_STATION in entry
    ]
