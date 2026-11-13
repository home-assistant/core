"""Constants for the Broadlink Magic Home integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "broadlink_magic_home"

CONF_FAMILY_ID: Final = "family_id"
CONF_FAMILY_NAME: Final = "family_name"
CONF_FAMILY_PID: Final = "family_pid"
CONF_FAMILY_TOKEN: Final = "family_token"
CONF_BLETOKEN: Final = "bletoken"
CONF_DEVICES: Final = "devices"
CONF_GATEWAYS: Final = "gateways"
CONF_GROUPS: Final = "groups"
CONF_ROOMS: Final = "rooms"
CONF_SCENES: Final = "scenes"
CONF_VIRTUAL_SUBTOKENS: Final = "virtual_subtokens"

IMPORT_PATH: Final = "/industry/v1/familyinfo/import"
IMPORT_TIMEOUT: Final = 180
UPDATE_INTERVAL: Final = timedelta(seconds=60)

PLATFORMS: Final = [Platform.CLIMATE]


def family_identifier(family_id: str) -> str:
    """Return the device identifier of an imported family."""
    return f"family:{family_id}"


def gateway_identifier(mac: str) -> str:
    """Return the device identifier of a family gateway."""
    return f"gateway:{mac}"


def device_identifier(stable_id: str) -> str:
    """Return the device identifier of an imported device."""
    return f"device:{stable_id}"


def rm_device_identifier(stable_id: str) -> str:
    """Return the device identifier of a device learned on an RM gateway."""
    return f"rm:{stable_id}"
