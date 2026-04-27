"""Constants for the Bitvis Power Hub integration."""

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .coordinator import BitvisListenerRegistry

DOMAIN = "bitvis"
MANUFACTURER = "Bitvis"
MODEL_NAME = "Power Hub"

ZEROCONF_SERVICE_TYPE = "_powerhub._udp.local."

DEFAULT_NAME = "Bitvis Power Hub"
DEFAULT_PORT = 58220

WATCHDOG_INTERVAL = timedelta(seconds=60)

DATA_LISTENER_REGISTRY: HassKey[BitvisListenerRegistry] = HassKey(DOMAIN)
