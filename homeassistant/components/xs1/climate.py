"""Support for XS1 climate devices."""

from __future__ import annotations

from typing import Any

from xs1_api_client.api_constants import ActuatorType
from xs1_api_client.device.actuator import XS1Actuator
from xs1_api_client.device.sensor import XS1Sensor

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ACTUATORS, DOMAIN, SENSORS
from .entity import XS1DeviceEntity


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the XS1 thermostat platform."""
    actuators: list[XS1Actuator] = hass.data[DOMAIN][ACTUATORS]
    sensors: list[XS1Sensor] = hass.data[DOMAIN][SENSORS]

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

            thermostat_entities.append(XS1ThermostatEntity(actuator, matching_sensor))

    add_entities(thermostat_entities)


class XS1ThermostatEntity(XS1DeviceEntity, ClimateEntity):
    """Representation of a XS1 thermostat."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 8
    _attr_max_temp = 25

    def __init__(self, device: XS1Actuator, sensor: XS1Sensor) -> None:
        """Initialize the actuator."""
        super().__init__(device)
        self.sensor = sensor

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self.device.name()

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.sensor is None:
            return None

        return self.sensor.value()

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return self.device.unit()

    @property
    def target_temperature(self) -> float | None:
        """Return the current target temperature."""
        return self.device.new_value()

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)

        self.device.set_value(temp)

        if self.sensor is not None:
            self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

    async def async_update(self) -> None:
        """Also update the sensor when available."""
        await super().async_update()
        if self.sensor is not None:
            await self.hass.async_add_executor_job(self.sensor.update)
