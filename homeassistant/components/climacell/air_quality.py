"""Weather component that handles meteorological data for your location."""
import logging
from typing import Callable, List

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import ClimaCellEntity
from .const import AQI_FIELD_LOOKUP, CONF_AQI_COUNTRY, CURRENT, DOMAIN

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entity = ClimaCellAirQualityEntity(config_entry, coordinator)

    async_add_entities([entity], update_before_add=True)


class ClimaCellAirQualityEntity(ClimaCellEntity, AirQualityEntity):
    """Entity that talks to ClimaCell API to retrieve air quality data."""

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._coordinator.data[CURRENT].get("pm25", {}).get("value")

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._coordinator.data[CURRENT].get("pm10", {}).get("value")

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return (
            self._coordinator.data[CURRENT]
            .get(AQI_FIELD_LOOKUP[self._config_entry.options[CONF_AQI_COUNTRY]], {})
            .get("value")
        )

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._coordinator.data[CURRENT].get("o3", {}).get("value")

    @property
    def carbon_monoxide(self):
        """Return the CO (carbon monoxide) level."""
        return self._coordinator.data[CURRENT].get("co", {}).get("value")

    @property
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        return self._coordinator.data[CURRENT].get("so2", {}).get("value")

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        return self._coordinator.data[CURRENT].get("no2", {}).get("value")
