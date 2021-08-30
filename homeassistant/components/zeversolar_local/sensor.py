"""Zever solar sensors."""
import logging

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, ZEVER_INVERTER_ID

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the hunter douglas shades sensors."""

    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[COORDINATOR]
    sensors = [
        ZeverSolarLocalTotalEnergySensor(coordinator, entry.data[ZEVER_INVERTER_ID]),
        ZeverSolarLocalCurrentPowerSensor(coordinator, entry.data[ZEVER_INVERTER_ID]),
    ]
    async_add_entities(sensors)


def _make_unique_id(zever_inverter_id: str, attr_device_class: str) -> str:
    return f"{zever_inverter_id}_{attr_device_class}"


class ZeverSolarSensor(CoordinatorEntity, SensorEntity):
    """Base class of a zeversolar sensor."""

    def __init__(self, coordinator, zever_inverter_id):
        """Init."""
        self._attr_unique_id = _make_unique_id(
            zever_inverter_id, self._attr_device_class
        )
        super().__init__(coordinator)


class ZeverSolarLocalTotalEnergySensor(ZeverSolarSensor):
    """Total generated solar energy."""

    _attr_device_class = DEVICE_CLASS_ENERGY
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_state_class = STATE_CLASS_TOTAL_INCREASING
    _attr_name = "total generated energy."

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor data."""
        return self.coordinator.data.daily_energy


class ZeverSolarLocalCurrentPowerSensor(ZeverSolarSensor):
    """Current solar power."""

    _attr_device_class = DEVICE_CLASS_POWER
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_name = "Current solar power production."

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor data."""

        return self.coordinator.data.current_power
