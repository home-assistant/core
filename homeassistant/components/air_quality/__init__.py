"""Component for handling Air Quality data for your location."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    ATTR_AQI,
    ATTR_CO,
    ATTR_CO2,
    ATTR_N2O,
    ATTR_NO,
    ATTR_NO2,
    ATTR_OZONE,
    ATTR_PM_0_1,
    ATTR_PM_2_5,
    ATTR_PM_10,
    ATTR_SO2,
    DOMAIN,
    AirQualityEntityStateAttribute,
)
from .entity import AirQualityEntity

_LOGGER: Final = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[AirQualityEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL: Final = timedelta(seconds=30)


__all__ = [
    "ATTR_AQI",
    "ATTR_CO",
    "ATTR_CO2",
    "ATTR_N2O",
    "ATTR_NO",
    "ATTR_NO2",
    "ATTR_OZONE",
    "ATTR_PM_0_1",
    "ATTR_PM_2_5",
    "ATTR_PM_10",
    "ATTR_SO2",
    "DOMAIN",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "AirQualityEntity",
    "AirQualityEntityStateAttribute",
]


# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the air quality component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[AirQualityEntity](
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
