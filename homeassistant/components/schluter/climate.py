"""Support for Schluter thermostats."""
import logging

from requests import RequestException
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    SCAN_INTERVAL,
    ClimateDevice,
)
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
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1))}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Schluter thermostats."""
    if discovery_info is None:
        return
    session_id = hass.data[DOMAIN][DATA_SCHLUTER_SESSION]
    api = hass.data[DOMAIN][DATA_SCHLUTER_API]
    temp_unit = hass.config.units.temperature_unit

    async def async_update_data():
        try:
            thermostats = await hass.async_add_executor_job(
                api.get_thermostats, session_id
            )
        except RequestException as err:
            raise UpdateFailed(f"Error communicating with Schluter API: {err}")

        if thermostats is None:
            return {}

        return {thermo.serial_number: thermo for thermo in thermostats}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="schluter",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_refresh()

    async_add_entities(
        SchluterThermostat(coordinator, serial_number, temp_unit, api, session_id)
        for serial_number, thermostat in coordinator.data.items()
    )


class SchluterThermostat(ClimateDevice):
    """Representation of a Schluter thermostat."""

    def __init__(self, coordinator, serial_number, temp_unit, api, session_id):
        """Initialize the thermostat."""
        self._unit = temp_unit
        self._coordinator = coordinator
        self._serial_number = serial_number
        self._api = api
        self._session_id = session_id
        self._support_flags = SUPPORT_TARGET_TEMPERATURE

    @property
    def available(self):
        """Return if thermostat is available."""
        return self._coordinator.last_update_success

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
        return self._serial_number

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._coordinator.data[self._serial_number].name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._coordinator.data[self._serial_number].temperature

    @property
    def hvac_mode(self):
        """Return current mode. Only heat available for floor thermostat."""
        return HVAC_MODE_HEAT

    @property
    def hvac_action(self):
        """Return current operation. Can only be heating or idle."""
        return (
            CURRENT_HVAC_HEAT
            if self._coordinator.data[self._serial_number].is_heating
            else CURRENT_HVAC_IDLE
        )

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._coordinator.data[self._serial_number].set_point_temp

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return [HVAC_MODE_HEAT]

    @property
    def min_temp(self):
        """Identify min_temp in Schluter API."""
        return self._coordinator.data[self._serial_number].min_temp

    @property
    def max_temp(self):
        """Identify max_temp in Schluter API."""
        return self._coordinator.data[self._serial_number].max_temp

    async def async_set_hvac_mode(self, hvac_mode):
        """Mode is always heating, so do nothing."""

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = None
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        serial_number = self._coordinator.data[self._serial_number].serial_number
        _LOGGER.debug("Setting thermostat temperature: %s", target_temp)

        try:
            if target_temp is not None:
                self._api.set_temperature(self._session_id, serial_number, target_temp)
        except RequestException as ex:
            _LOGGER.error("An error occurred while setting temperature: %s", ex)

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self._coordinator.async_remove_listener(self.async_write_ha_state)
