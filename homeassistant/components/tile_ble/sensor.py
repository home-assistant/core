"""Sensor for the Tile BLE integration."""

from typing import override

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_last_service_info,
    async_register_advertisement_callback,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TileBleConfigEntry, TileBleCoordinator
from .entity import TileBleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TileBleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tile BLE sensor."""
    async_add_entities([TileBleSignalStrengthSensor(entry.runtime_data, entry.title)])


class TileBleSignalStrengthSensor(TileBleEntity, SensorEntity):
    """Reports the signal strength of the Tile's advertisements."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TileBleCoordinator, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, name)
        self._attr_unique_id = f"{coordinator.address}_signal_strength"

    @override
    async def async_added_to_hass(self) -> None:
        """Follow every advertisement, as the coordinator skips unchanged data."""
        await super().async_added_to_hass()
        if service_info := async_last_service_info(
            self.hass, self.coordinator.address, connectable=False
        ):
            self._attr_native_value = service_info.rssi
        self.async_on_remove(
            async_register_advertisement_callback(
                self.hass, self._handle_advertisement, self.coordinator.address
            )
        )

    @callback
    def _handle_advertisement(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Update the RSSI from an advertisement of the preferred source.

        Every adapter and proxy that sees the Tile reports its advertisements,
        so taking the RSSI of all of them would make it jump between sources.
        """
        preferred = async_last_service_info(
            self.hass, self.coordinator.address, connectable=False
        )
        if (
            preferred is not None and service_info.source != preferred.source
        ) or service_info.rssi == self._attr_native_value:
            return
        self._attr_native_value = service_info.rssi
        self.async_write_ha_state()
