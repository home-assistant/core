"""Battery sensor for the Nuki Lock."""

from __future__ import annotations

from pynuki.device import NukiDevice

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NukiEntryData
from .const import DOMAIN as NUKI_DOMAIN
from .entity import NukiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nuki lock sensor."""
    entry_data: NukiEntryData = hass.data[NUKI_DOMAIN][entry.entry_id]

    async_add_entities(
        NukiBatterySensor(entry_data.coordinator, lock) for lock in entry_data.locks
    )


class NukiBatterySensor(NukiEntity[NukiDevice], SensorEntity):
    """Representation of a Nuki Lock Battery sensor."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._nuki_device.nuki_id}_battery_level"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._nuki_device.battery_charge
