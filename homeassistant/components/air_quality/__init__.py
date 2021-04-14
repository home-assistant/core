"""Component for handling Air Quality data for your location."""
from datetime import timedelta
import logging
from typing import final

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
)
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

_LOGGER = logging.getLogger(__name__)

ATTR_AQI = "air_quality_index"
ATTR_CO2 = "carbon_dioxide"
ATTR_CO = "carbon_monoxide"
ATTR_N2O = "nitrogen_oxide"
ATTR_NO = "nitrogen_monoxide"
ATTR_NO2 = "nitrogen_dioxide"
ATTR_OZONE = "ozone"
ATTR_PM_0_1 = "particulate_matter_0_1"
ATTR_PM_10 = "particulate_matter_10"
ATTR_PM_2_5 = "particulate_matter_2_5"
ATTR_SO2 = "sulphur_dioxide"

DOMAIN = "air_quality"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(seconds=30)

PROP_TO_ATTR = {
    "air_quality_index": ATTR_AQI,
    "attribution": ATTR_ATTRIBUTION,
    "carbon_dioxide": ATTR_CO2,
    "carbon_monoxide": ATTR_CO,
    "nitrogen_oxide": ATTR_N2O,
    "nitrogen_monoxide": ATTR_NO,
    "nitrogen_dioxide": ATTR_NO2,
    "ozone": ATTR_OZONE,
    "particulate_matter_0_1": ATTR_PM_0_1,
    "particulate_matter_10": ATTR_PM_10,
    "particulate_matter_2_5": ATTR_PM_2_5,
    "sulphur_dioxide": ATTR_SO2,
}


async def async_setup(hass, config):
    """Set up the air quality component."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class AirQualityEntity(Entity):
    """ABC for air quality data."""

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        raise NotImplementedError()

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return None

    @property
    def particulate_matter_0_1(self):
        """Return the particulate matter 0.1 level."""
        return None

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return None

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return None

    @property
    def carbon_monoxide(self):
        """Return the CO (carbon monoxide) level."""
        return None

    @property
    def carbon_dioxide(self):
        """Return the CO2 (carbon dioxide) level."""
        return None

    @property
    def attribution(self):
        """Return the attribution."""
        return None

    @property
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        return None

    @property
    def nitrogen_oxide(self):
        """Return the N2O (nitrogen oxide) level."""
        return None

    @property
    def nitrogen_monoxide(self):
        """Return the NO (nitrogen monoxide) level."""
        return None

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        return None

    @final
    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data

    @property
    def state(self):
        """Return the current state."""
        return self.particulate_matter_2_5

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
