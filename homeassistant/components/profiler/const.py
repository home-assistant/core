"""Consts used by profiler."""

from homeassistant.core import CALLBACK_TYPE
from homeassistant.util.hass_dict import HassKey

DOMAIN = "profiler"
DATA_PROFILER: HassKey[dict[str, CALLBACK_TYPE]] = HassKey(DOMAIN)
DEFAULT_NAME = "Profiler"
