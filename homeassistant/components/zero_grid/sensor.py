"""Sensor entities for ZeroGrid."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZeroGrid sensor platform."""
    _LOGGER.debug("Setting up ZeroGrid sensor platform")

    available_load_sensor = AvailableAmpsSensor()
    controlled_load_sensor = LoadControlAmpsSensor()

    # Store references in hass.data for updates
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["available_load_sensor"] = available_load_sensor
    hass.data[DOMAIN]["controlled_load_sensor"] = controlled_load_sensor

    async_add_entities([available_load_sensor, controlled_load_sensor])


class AvailableAmpsSensor(SensorEntity):
    """Sensor for current available for load control."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_should_poll = False

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._attr_name = "Available load"
        self._attr_unique_id = f"{DOMAIN}_available_load"
        self._attr_native_value = 0.0

    @callback
    def update_value(self, amps: float) -> None:
        """Update the sensor value and notify HA."""
        self._attr_native_value = round(amps, 2)
        self.async_write_ha_state()


class LoadControlAmpsSensor(SensorEntity):
    """Sensor for total current controlled by load control."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_should_poll = False

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._attr_name = "Controlled load"
        self._attr_unique_id = f"{DOMAIN}_controlled_load"
        self._attr_native_value = 0.0

    @callback
    def update_value(self, amps: float) -> None:
        """Update the sensor value and notify HA."""
        self._attr_native_value = round(amps, 2)
        self.async_write_ha_state()
