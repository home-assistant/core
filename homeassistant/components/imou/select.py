"""Support for Imou select entities."""

from typing import override

from pyimouapi.const import (
    PARAM_CURRENT_OPTION,
    PARAM_DEVICE_VOLUME,
    PARAM_NIGHT_VISION_MODE,
    PARAM_OPTIONS,
)
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity
from .helpers import async_wrap_imou_command

PARALLEL_UPDATES = 0

SELECT_TYPES: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key=PARAM_DEVICE_VOLUME,
        entity_category=EntityCategory.CONFIG,
        translation_key=PARAM_DEVICE_VOLUME,
    ),
    SelectEntityDescription(
        key=PARAM_NIGHT_VISION_MODE,
        entity_category=EntityCategory.CONFIG,
        translation_key=PARAM_NIGHT_VISION_MODE,
    ),
)


def _iter_selects(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[SelectEntityDescription, ImouHaDevice]]:
    """Return (description, device) pairs for supported selects."""
    return [
        (description, device)
        for device in coordinator.devices
        for description in SELECT_TYPES
        if description.key in device.selects
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou select entities."""
    coordinator = entry.runtime_data

    def _add_selects(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouSelect(coordinator, description, device)
            for description, device in _iter_selects(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    entry.async_on_unload(coordinator.register_new_device_callback(_add_selects))
    _add_selects(coordinator.devices)


class ImouSelect(ImouEntity, SelectEntity):
    """Imou select entity."""

    entity_description: SelectEntityDescription

    @property
    @override
    def options(self) -> list[str]:
        """Return a list of selectable options."""
        return self.device.selects[self._entity_type][PARAM_OPTIONS]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.device.selects[self._entity_type][PARAM_CURRENT_OPTION]

    @override
    @async_wrap_imou_command("select_option_failed")
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.device_manager.async_select_option(
            self.device,
            self._entity_type,
            option,
        )
        await self.coordinator.async_request_refresh()
