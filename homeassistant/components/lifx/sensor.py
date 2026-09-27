"""Sensors for LIFX lights."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_RSSI
from .coordinator import LIFXConfigEntry, LIFXUpdateCoordinator
from .entity import LIFXEntity

PARALLEL_UPDATES = 0

RSSI_SENSOR = SensorEntityDescription(
    key=ATTR_RSSI,
    translation_key="rssi",
    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LIFX sensor from config entry."""
    coordinator = entry.runtime_data
    async_add_entities([LIFXRssiSensor(coordinator, RSSI_SENSOR)])


class LIFXRssiSensor(LIFXEntity, SensorEntity):
    """LIFX RSSI sensor."""

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise the RSSI sensor."""

        super().__init__(coordinator, description)
        self._attr_native_unit_of_measurement = coordinator.rssi_uom
        self._async_update_attrs()

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        self._attr_native_value = self.coordinator.rssi

    @override
    async def async_added_to_hass(self) -> None:
        """Enable RSSI updates."""
        self.async_on_remove(self.coordinator.async_enable_rssi_updates())
        return await super().async_added_to_hass()
