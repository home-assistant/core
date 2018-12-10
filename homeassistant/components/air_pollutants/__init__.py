"""
Component for handling Air Pollutants data for your location.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/air_pollutants/
"""
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'air_pollutants'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

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


async def async_setup(hass, config):
    """Set up the air pollutants component."""
    component = hass.data[DOMAIN] = EntityComponent(_LOGGER, DOMAIN, hass)
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
    def temperature_unit(self):
        """Return the unit of measurement of the temperature."""
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

        air_quality_index = self.air_quality_index
        if air_quality_index is not None:
            data[ATTR_AIR_POLLUTANTS_AQI] = air_quality_index

        ozone = self.ozone
        if ozone is not None:
            data[ATTR_AIR_POLLUTANTS_OZONE] = ozone

        particulate_matter_0_1 = self.particulate_matter_0_1
        if particulate_matter_0_1 is not None:
            data[ATTR_AIR_POLLUTANTS_PM_0_1] = particulate_matter_0_1

        particulate_matter_10 = self.particulate_matter_10
        if particulate_matter_10 is not None:
            data[ATTR_AIR_POLLUTANTS_PM_10] = particulate_matter_10

        sulphur_dioxide = self.sulphur_dioxide
        if sulphur_dioxide is not None:
            data[ATTR_AIR_POLLUTANTS_SO2] = sulphur_dioxide

        nitrogen_oxide = self.nitrogen_oxide
        if nitrogen_oxide is not None:
            data[ATTR_AIR_POLLUTANTS_N2O] = nitrogen_oxide

        nitrogen_monoxide = self.nitrogen_monoxide
        if nitrogen_monoxide is not None:
            data[ATTR_AIR_POLLUTANTS_NO] = nitrogen_monoxide

        nitrogen_dioxide = self.nitrogen_dioxide
        if nitrogen_dioxide is not None:
            data[ATTR_AIR_POLLUTANTS_NO2] = nitrogen_dioxide

        carbon_dioxide = self.carbon_dioxide
        if carbon_dioxide is not None:
            data[ATTR_AIR_POLLUTANTS_C02] = carbon_dioxide

        carbon_monoxide = self.carbon_monoxide
        if carbon_monoxide is not None:
            data[ATTR_AIR_POLLUTANTS_CO] = carbon_monoxide

        attribution = self.attribution
        if attribution is not None:
            data[ATTR_AIR_POLLUTANTS_ATTRIBUTION] = attribution

        return data

    @property
    def state(self):
        """Return the current state."""
        return self.particulate_matter_2_5
