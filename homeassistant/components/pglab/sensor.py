"""Sensor for PG LAB Electronics."""
from __future__ import annotations

from typing import Any

from pypglab.const import SENSOR_TEMPERATURE, SENSOR_VOLTAGE
from pypglab.device import Device
from pypglab.sensor import Sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CREATE_NEW_ENTITY, DISCONNECT_COMPONENT
from .entity import BaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor for device."""

    @callback
    def async_discover(
        sensor_type: str, pglab_device: Device, pglab_sensor: Sensor
    ) -> None:
        """Discover and add a PG LAB Relay."""
        pglab_sensor = PgLab_Sensor(sensor_type, pglab_device, pglab_sensor)
        async_add_entities([pglab_sensor])

    hass.data[DISCONNECT_COMPONENT[Platform.SENSOR]] = async_dispatcher_connect(
        hass, CREATE_NEW_ENTITY[Platform.SENSOR], async_discover
    )


DEVICE_CLASS = "device_class"
STATE_CLASS = "state_class"
ICON = "icon"
UNIT = "unit"

SENSOR_INFO: dict[str, dict[str, Any]] = {
    SENSOR_TEMPERATURE: {
        DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
        ICON: None,
        UNIT: UnitOfTemperature.CELSIUS,
    },
    SENSOR_VOLTAGE: {
        DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
        ICON: None,
        UNIT: UnitOfElectricPotential.VOLT,
    },
}


class PgLab_Sensor(BaseEntity, SensorEntity):
    """A PG Lab Sensor."""

    def __init__(
        self, sensor_type: str, pglab_device: Device, pglab_sensor: Sensor
    ) -> None:
        """Initialize the Sensor class."""

        super().__init__(
            platform=Platform.SENSOR, device=pglab_device, entity=pglab_sensor
        )

        self._attr_unique_id = f"{pglab_device.id}_{sensor_type}"
        self._attr_name = f"{pglab_device.name}_{sensor_type}"

        self._sensor = pglab_sensor
        self._type = sensor_type
        self._state: Any | None = self._sensor.state[self._type]

        sensor_info = SENSOR_INFO[sensor_type]

        self._attr_device_class = sensor_info.get(DEVICE_CLASS)
        self._attr_state_class = sensor_info.get(STATE_CLASS)
        self._attr_icon = sensor_info.get(ICON)
        self._attr_native_unit_of_measurement = sensor_info.get(UNIT)

    @callback
    def state_updated(self, payload: str) -> None:
        """Handle state updates."""
        self._state = self._sensor.state[self._type]
        super().state_updated(payload)

    @property
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        return self._state
