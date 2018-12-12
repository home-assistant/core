"""
Support for XS1 climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xs1/
"""
from functools import partial
import logging

from homeassistant.components.climate import ATTR_TEMPERATURE, ClimateDevice
from homeassistant.components.xs1 import (
    ACTUATORS, DOMAIN, SENSORS, XS1DeviceEntity)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.util.temperature import convert as convert_temperature

DEPENDENCIES = ['xs1']
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the XS1 platform."""
    _LOGGER.debug("initializing XS1 Thermostat")

    from xs1_api_client.api_constants import ActuatorType

    actuators = hass.data[DOMAIN][ACTUATORS]
    sensors = hass.data[DOMAIN][SENSORS]

    thermostat_entities = []
    for actuator in actuators:
        if actuator.type() == ActuatorType.TEMPERATURE:
            # Search for a matching sensor (by name)
            actuator_name = actuator.name()

            matching_sensor = None
            for sensor in sensors:
                if actuator_name in sensor.name():
                    matching_sensor = sensor

                    break

            thermostat_entities.append(
                XS1ThermostatEntity(actuator, matching_sensor, 8, 25))

    async_add_devices(thermostat_entities)

    _LOGGER.debug("Added Thermostats!")


class XS1ThermostatEntity(XS1DeviceEntity, ClimateDevice):
    """Representation of a XS1 thermostat."""

    def __init__(self, device, sensor, min_temp: int, max_temp: int):
        """Initialize the actuator."""
        super().__init__(device)
        self.sensor = sensor

        self._min_temp = min_temp
        self._max_temp = max_temp

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.device.name()

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self.sensor is None:
            return None

        return self.sensor.value()

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return self.device.unit()

    @property
    def target_temperature(self):
        """Return the current target temperature."""
        return self.device.new_value()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(
            self._min_temp,
            TEMP_CELSIUS,
            self.unit_of_measurement
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(
            self._max_temp,
            TEMP_CELSIUS,
            self.unit_of_measurement
        )

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)

        await self.hass.async_add_executor_job(
            partial(self.device.set_value, temp))

        if self.sensor is not None:
            self.async_schedule_update_ha_state()

    async def async_update(self):
        """Also update the sensor when available."""
        await super().async_update()
        if self.sensor is not None:
            await self.hass.async_add_executor_job(
                partial(self.sensor.update))
