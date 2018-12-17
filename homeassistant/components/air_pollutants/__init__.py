"""
Component for handling Air Pollutants data for your location.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/air_pollutants/
"""
from datetime import timedelta
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_AIR_POLLUTANTS_AQI = 'air_quality_index'
ATTR_AIR_POLLUTANTS_ATTRIBUTION = 'attribution'
ATTR_AIR_POLLUTANTS_C02 = 'carbon_dioxide'
ATTR_AIR_POLLUTANTS_CO = 'carbon_monoxide'
ATTR_AIR_POLLUTANTS_N2O = 'nitrogen_oxide'
ATTR_AIR_POLLUTANTS_NO = 'nitrogen_monoxide'
ATTR_AIR_POLLUTANTS_NO2 = 'nitrogen_dioxide'
ATTR_AIR_POLLUTANTS_OZONE = 'ozone'
ATTR_AIR_POLLUTANTS_PM_0_1 = 'particulate_matter_0_1'
ATTR_AIR_POLLUTANTS_PM_10 = 'particulate_matter_10'
ATTR_AIR_POLLUTANTS_PM_2_5 = 'particulate_matter_2_5'
ATTR_AIR_POLLUTANTS_SO2 = 'sulphur_dioxide'

DOMAIN = 'air_pollutants'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=30)

PROP_TO_ATTR = {
    'air_quality_index': ATTR_AIR_POLLUTANTS_AQI,
    'attribution': ATTR_AIR_POLLUTANTS_ATTRIBUTION,
    'carbon_dioxide': ATTR_AIR_POLLUTANTS_C02,
    'carbon_monoxide': ATTR_AIR_POLLUTANTS_CO,
    'nitrogen_oxide': ATTR_AIR_POLLUTANTS_N2O,
    'nitrogen_monoxide': ATTR_AIR_POLLUTANTS_NO,
    'nitrogen_dioxide': ATTR_AIR_POLLUTANTS_NO2,
    'ozone': ATTR_AIR_POLLUTANTS_OZONE,
    'particulate_matter_0_1': ATTR_AIR_POLLUTANTS_PM_0_1,
    'particulate_matter_10': ATTR_AIR_POLLUTANTS_PM_10,
    'particulate_matter_2_5': ATTR_AIR_POLLUTANTS_PM_2_5,
    'sulphur_dioxide': ATTR_AIR_POLLUTANTS_SO2,
}


async def async_setup(hass, config):
    """Set up the air pollutants component."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    await component.async_setup(config)
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class AirPollutantsEntity(Entity):
    """ABC for air pollutants data."""

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
