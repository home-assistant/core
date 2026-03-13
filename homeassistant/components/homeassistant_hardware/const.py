"""Constants for the Homeassistant Hardware integration."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .helpers import HardwareInfoDispatcher


LOGGER = logging.getLogger(__package__)

DOMAIN = "homeassistant_hardware"
DATA_COMPONENT: HassKey[HardwareInfoDispatcher] = HassKey(DOMAIN)

ZHA_DOMAIN = "zha"
OTBR_DOMAIN = "otbr"

HARDWARE_INTEGRATION_DOMAINS = {
    "homeassistant_sky_connect",
    "homeassistant_connect_zbt2",
    "homeassistant_yellow",
}

OTBR_ADDON_NAME = "OpenThread Border Router"
OTBR_ADDON_MANAGER_DATA = "openthread_border_router"
OTBR_ADDON_SLUG = "core_openthread_border_router"

ZIGBEE_FLASHER_ADDON_NAME = "Silicon Labs Flasher"
ZIGBEE_FLASHER_ADDON_MANAGER_DATA = "silabs_flasher"
ZIGBEE_FLASHER_ADDON_SLUG = "core_silabs_flasher"

SILABS_MULTIPROTOCOL_ADDON_SLUG = "core_silabs_multiprotocol"
SILABS_FLASHER_ADDON_SLUG = "core_silabs_flasher"

Z2M_EMBER_DOCS_URL = "https://www.zigbee2mqtt.io/guide/adapters/emberznet.html"

# Community add-ons use an 8-char repository hash prefix in their slug
Z2M_ADDON_NAME = "Zigbee2MQTT"
Z2M_ADDON_SLUG_REGEX = re.compile(r"^[0-9a-f]{8}_zigbee2mqtt(?:_edge)?$")
