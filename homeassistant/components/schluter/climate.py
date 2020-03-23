"""Support for Schluter thermostats."""
from datetime import timedelta
import logging

from requests import RequestException
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import DATA_SCHLUTER_API, DATA_SCHLUTER_SESSION, DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=5)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1))}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Schluter thermostats."""
    session_id = hass.data[DOMAIN][DATA_SCHLUTER_SESSION]
    api = hass.data[DOMAIN][DATA_SCHLUTER_API]
    temp_unit = hass.config.units.temperature_unit

    async def async_update_data():
        try:
            return api.get_thermostats(session_id) or []
        except RequestException as err:
            raise UpdateFailed(f"Error communicating with Schluter API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="schluter",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_refresh()

    async_add_entities(
        SchluterThermostat(coordinator, idx, temp_unit, api, session_id)
        for idx, ent in enumerate(coordinator.data)
    )


class SchluterThermostat(ClimateDevice):
    """Representation of a Schluter thermostat."""

    def __init__(self, coordinator, idx, temp_unit, api, session_id):
        """Initialize the thermostat."""
        self._unit = temp_unit
        self.coordinator = coordinator
        self.idx = idx
        self._api = api
        self._session_id = session_id
        self._support_flags = SUPPORT_TARGET_TEMPERATURE

    @property
    def should_poll(self):
        """Return if platform should poll."""
        return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self.coordinator.data[self.idx].serial_number

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.data[self.idx].serial_number)},
            "name": self.coordinator.data[self.idx].name,
            "manufacturer": "Schluter",
            "model": "Thermostat",
            "sw_version": self.coordinator.data[self.idx].sw_version,
        }

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self.coordinator.data[self.idx].name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.coordinator.data[self.idx].temperature

    @property
    def hvac_mode(self):
        """Return current mode. Only heat available for floor thermostat."""
        return HVAC_MODE_HEAT

    @property
    def hvac_action(self):
        """Return current operation. Can only be heating or idle."""
        return (
            CURRENT_HVAC_HEAT
            if self.coordinator.data[self.idx].is_heating
            else CURRENT_HVAC_IDLE
        )

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.coordinator.data[self.idx].set_point_temp

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return None

    @property
    def min_temp(self):
        """Identify min_temp in Schluter API."""
        return self.coordinator.data[self.idx].min_temp

    @property
    def max_temp(self):
        """Identify max_temp in Schluter API."""
        return self.coordinator.data[self.idx].max_temp

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = None
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        serial_number = self.coordinator.data[self.idx].serial_number
        _LOGGER.debug("Setting thermostat temperature: %s", target_temp)

        try:
            if target_temp is not None:
                self._api.set_temperature(self._session_id, serial_number, target_temp)
        except RequestException as ex:
            _LOGGER.error("An error occurred while setting temperature: %s", ex)
            self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)
