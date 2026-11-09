"""Support for Geolocation."""

from datetime import timedelta
from functools import partial
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityStateAttribute
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import (
    DeprecatedConstant,
    DeprecatedConstantEnum,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, GeolocationEntityStateAttribute
from .entity import GeolocationEvent

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[GeolocationEvent]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)


_DEPRECATED_ATTR_DISTANCE = DeprecatedConstant("distance", None, "2027.12")
_DEPRECATED_ATTR_LATITUDE = DeprecatedConstantEnum(
    EntityStateAttribute.LATITUDE, "2027.12"
)
_DEPRECATED_ATTR_LONGITUDE = DeprecatedConstantEnum(
    EntityStateAttribute.LONGITUDE, "2027.12"
)
_DEPRECATED_ATTR_SOURCE = DeprecatedConstantEnum(
    GeolocationEntityStateAttribute.SOURCE, "2027.12"
)

__all__ = [
    "ATTR_DISTANCE",
    "ATTR_LATITUDE",
    "ATTR_LONGITUDE",
    "ATTR_SOURCE",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "GeolocationEntityStateAttribute",
    "GeolocationEvent",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Geolocation component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[GeolocationEvent](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
