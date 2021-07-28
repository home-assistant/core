"""Demo platform that has a couple of fake sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Demo sensors."""
    async_add_entities(
        [
            DemoSensor(
                "sensor_1",
                "Outside Temperature",
                15.6,
                DEVICE_CLASS_TEMPERATURE,
                STATE_CLASS_MEASUREMENT,
                TEMP_CELSIUS,
                12,
            ),
            DemoSensor(
                "sensor_2",
                "Outside Humidity",
                54,
                DEVICE_CLASS_HUMIDITY,
                STATE_CLASS_MEASUREMENT,
                PERCENTAGE,
                None,
            ),
            DemoSensor(
                "sensor_3",
                "Carbon monoxide",
                54,
                DEVICE_CLASS_CO,
                STATE_CLASS_MEASUREMENT,
                CONCENTRATION_PARTS_PER_MILLION,
                None,
            ),
            DemoSensor(
                "sensor_4",
                "Carbon dioxide",
                54,
                DEVICE_CLASS_CO2,
                STATE_CLASS_MEASUREMENT,
                CONCENTRATION_PARTS_PER_MILLION,
                14,
            ),
            DemoSensor(
                "sensor_5",
                "Power consumption",
                100,
                DEVICE_CLASS_POWER,
                STATE_CLASS_MEASUREMENT,
                POWER_WATT,
                None,
            ),
            DemoSensor(
                "sensor_6",
                "Today energy",
                15,
                DEVICE_CLASS_ENERGY,
                STATE_CLASS_MEASUREMENT,
                ENERGY_KILO_WATT_HOUR,
                None,
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoSensor(SensorEntity):
    """Representation of a Demo sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        state: StateType,
        device_class: str | None,
        state_class: str | None,
        unit_of_measurement: str | None,
        battery: StateType,
    ) -> None:
        """Initialize the sensor."""
        self._attr_device_class = device_class
        self._attr_name = name
        self._attr_state = state
        self._attr_state_class = state_class
        self._attr_unique_id = unique_id
        self._attr_unit_of_measurement = unit_of_measurement

        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_id)},
            "name": name,
        }

        if battery:
            self._attr_extra_state_attributes = {ATTR_BATTERY_LEVEL: battery}
