"""Meter connectivity for Rainforest Eagle gateways."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_TYPE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TYPE_EAGLE_200
from .coordinator import EagleDataCoordinator, RainforestEagleConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainforestEagleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up meter connectivity for gateways that report it."""
    if entry.data[CONF_TYPE] == TYPE_EAGLE_200:
        async_add_entities([EagleMeterConnectivity(entry.runtime_data)])


class EagleMeterConnectivity(
    CoordinatorEntity[EagleDataCoordinator], BinarySensorEntity
):
    """Represent the connection between an EAGLE gateway and its meter."""

    _attr_has_entity_name = True
    _attr_translation_key = "meter_connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: EagleDataCoordinator) -> None:
        """Initialize the meter connectivity sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.cloud_id}-${coordinator.hardware_address}-meter_connectivity"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.cloud_id)},
            manufacturer="Rainforest Automation",
            model=coordinator.model,
            name=coordinator.model,
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the gateway is connected to its meter."""
        return self.coordinator.is_connected
