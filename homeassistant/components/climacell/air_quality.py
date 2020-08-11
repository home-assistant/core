"""Weather component that handles meteorological data for your location."""
import logging
from typing import Callable, List

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import ClimaCellEntity, get_cc_value
from .const import (
    AQI_FIELD_LOOKUP,
    CC_ATTR_CARBON_MONOXIDE,
    CC_ATTR_NITROGEN_DIOXIDE,
    CC_ATTR_OZONE,
    CC_ATTR_PM_2_5,
    CC_ATTR_PM_10,
    CC_ATTR_SULPHUR_DIOXIDE,
    CONF_AQI_COUNTRY,
    CURRENT,
    DOMAIN,
)

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
        return get_cc_value(self._coordinator.data[CURRENT], CC_ATTR_PM_2_5)

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return get_cc_value(self._coordinator.data[CURRENT], CC_ATTR_PM_10)

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return get_cc_value(
            self._coordinator.data[CURRENT],
            AQI_FIELD_LOOKUP[self._config_entry.options[CONF_AQI_COUNTRY]],
        )

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return get_cc_value(self._coordinator.data[CURRENT], CC_ATTR_OZONE)

    @property
    def carbon_monoxide(self):
        """Return the CO (carbon monoxide) level."""
        return get_cc_value(self._coordinator.data[CURRENT], CC_ATTR_CARBON_MONOXIDE)

    @property
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        return get_cc_value(self._coordinator.data[CURRENT], CC_ATTR_SULPHUR_DIOXIDE)

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        return get_cc_value(self._coordinator.data[CURRENT], CC_ATTR_NITROGEN_DIOXIDE)

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return False
