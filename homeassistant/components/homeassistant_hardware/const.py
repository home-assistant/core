"""Constants for the Homeassistant Hardware integration."""

from __future__ import annotations

import logging
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

# Popular ones taken from https://analytics.home-assistant.io/addons.json
Z2M_ADDON_NAME = "Zigbee2MQTT"
Z2M_ADDON_SLUGS = {
    "486e6e9b_zigbee2mqtt",
    "45df7312_zigbee2mqtt_edge",
    "9336c2b0_zigbee2mqtt",
    "8c77aaed_zigbee2mqtt",
}
