"""Sensors for LIFX lights."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_RSSI, DOMAIN
from .coordinator import LIFXUpdateCoordinator
from .entity import LIFXEntity

SCAN_INTERVAL = timedelta(seconds=30)

RSSI_SENSOR = SensorEntityDescription(
    key=ATTR_RSSI,
    translation_key="rssi",
    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LIFX sensor from config entry."""
    coordinator: LIFXUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LIFXRssiSensor(coordinator, RSSI_SENSOR)])


class LIFXRssiSensor(LIFXEntity, SensorEntity):
    """LIFX RSSI sensor."""

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise the RSSI sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._attr_native_unit_of_measurement = coordinator.rssi_uom

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        self._attr_native_value = self.coordinator.rssi

    @callback
    async def async_added_to_hass(self) -> None:
        """Enable RSSI updates."""
        self.async_on_remove(self.coordinator.async_enable_rssi_updates())
        return await super().async_added_to_hass()
