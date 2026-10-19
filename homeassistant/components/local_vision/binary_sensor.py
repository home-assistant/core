"""Binary sensor for Local vision."""

from typing import override

from tarsius import Status

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LocalVisionConfigEntry, LocalVisionCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LocalVisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor."""
    device = async_entity_id_to_device(hass, entry.options[CONF_ENTITY_ID])
    async_add_entities([LocalVisionBinarySensor(entry.runtime_data, device)])


class LocalVisionBinarySensor(
    CoordinatorEntity[LocalVisionCoordinator], BinarySensorEntity
):
    """State of a camera region."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: LocalVisionCoordinator, device: AnyDeviceEntry | None
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_name = entry.title
        self._attr_unique_id = entry.entry_id
        self._attr_device_class = BinarySensorDeviceClass(
            entry.options[CONF_DEVICE_CLASS]
        )
        self.device_entry = device

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state, None while unsure or not taught."""
        result = self.coordinator.data
        if result.status is not Status.CONFIDENT:
            return None
        return result.state == STATE_ON
