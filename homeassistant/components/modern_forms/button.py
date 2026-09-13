"""Support for Modern Forms buttons."""

from typing import override

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import modernforms_exception_handler
from .coordinator import ModernFormsConfigEntry, ModernFormsDataUpdateCoordinator
from .entity import ModernFormsDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ModernFormsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Modern Forms buttons based on a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities([ModernFormsRestartButton(config_entry.entry_id, coordinator)])


class ModernFormsRestartButton(ModernFormsDeviceEntity, ButtonEntity):
    """Defines a Modern Forms restart button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, entry_id: str, coordinator: ModernFormsDataUpdateCoordinator
    ) -> None:
        """Initialize the restart button."""
        super().__init__(entry_id=entry_id, coordinator=coordinator)
        self._attr_unique_id = f"{self.coordinator.data.info.mac_address}_restart"

    @modernforms_exception_handler
    @override
    async def async_press(self) -> None:
        """Reboot the fan."""
        await self.coordinator.modern_forms.reboot()
