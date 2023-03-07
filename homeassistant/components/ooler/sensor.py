"""Support for Ooler Sleep System sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import OolerData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ooler sensors."""
    data: OolerData = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        OolerWattageSensorEntity(data),
        OolerWaterLevelSensorEntity(data),
    ]
    async_add_entities(entities)


class OolerSensorEntity(SensorEntity):
    """Representation of an Ooler sensor."""

    _attr_has_entity_name = True

    def __init__(self, data: OolerData) -> None:
        """Initialize the sensor entity."""
        self._data = data
        self._attr_device_info = DeviceInfo(
            name=data.model, connections={(dr.CONNECTION_BLUETOOTH, data.address)}
        )

    @property
    def available(self) -> bool:
        """Determine if the entity is available."""
        return self._data.client.is_connected

    @callback
    def _handle_state_update(self, *args: Any) -> None:
        """Handle state update."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore state on start up and register callback."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._data.client.register_callback(self._handle_state_update)
        )


class OolerWattageSensorEntity(OolerSensorEntity):
    """Representation of an Ooler wattage sensor."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER

    def __init__(self, data: OolerData) -> None:
        """Initialize the wattage sensor entity."""
        super().__init__(data)
        self._attr_name = "Wattage"
        self._attr_unique_id = f"{data.address}_wattage_sensor"

    @property
    def native_value(self) -> int | None:
        """Return the wattage of the pump."""
        if self._data.client.state is not None:
            return self._data.client.state.pump_watts
        return None

    @property
    def suggested_unit_of_measurement(self) -> str | None:
        """Return the suggested unit of measurement for power."""
        return UnitOfPower.WATT


class OolerWaterLevelSensorEntity(OolerSensorEntity):
    """Representation of an Ooler water level sensor."""

    _attr_native_unit_of_measurement = "%"

    def __init__(self, data: OolerData) -> None:
        """Initialize the water level sensor entity."""
        super().__init__(data)
        self._attr_name = "Water Level"
        self._attr_unique_id = f"{data.address}_water_level_sensor"

    @property
    def native_value(self) -> int | None:
        """Return the water level of the Ooler."""
        return self._data.client.state.water_level
