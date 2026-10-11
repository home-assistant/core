"""Support for buttons."""

from typing import override

from fjaraskupan import COMMAND_RESETGREASEFILTER

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import async_setup_entry_platform
from .coordinator import FjaraskupanConfigEntry, FjaraskupanCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FjaraskupanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities dynamically through discovery."""

    def _constructor(coordinator: FjaraskupanCoordinator) -> list[Entity]:
        return [
            ResetGreaseFilter(coordinator, coordinator.device_info),
        ]

    async_setup_entry_platform(hass, config_entry, async_add_entities, _constructor)


class ResetGreaseFilter(CoordinatorEntity[FjaraskupanCoordinator], ButtonEntity):
    """Reset the grease filter indicator."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "reset_grease_filter"

    def __init__(
        self,
        coordinator: FjaraskupanCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Init button entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}-reset-grease-filter"
        self._attr_device_info = device_info

    @override
    async def async_press(self) -> None:
        """Reset the grease filter."""
        async with self.coordinator.async_connect_and_update() as device:
            await device.send_command(COMMAND_RESETGREASEFILTER)
            await device.update()
