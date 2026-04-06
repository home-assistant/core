"""Button platform for BSB-Lan integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BSBLanConfigEntry, BSBLanData
from .coordinator import BSBLanFastCoordinator
from .entity import BSBLanEntity
from .helpers import async_sync_device_time

PARALLEL_UPDATES = 1

BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="sync_time",
        translation_key="sync_time",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BSBLanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BSB-Lan button entities from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        BSBLanButtonEntity(data.fast_coordinator, data, description)
        for description in BUTTON_DESCRIPTIONS
    )


class BSBLanButtonEntity(BSBLanEntity, ButtonEntity):
    """Defines a BSB-Lan button entity."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: BSBLanFastCoordinator,
        data: BSBLanData,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize BSB-Lan button entity."""
        super().__init__(coordinator, data)
        self.entity_description = description
        self._attr_unique_id = f"{data.device.MAC}-{description.key}"
        self._data = data

    async def async_press(self) -> None:
        """Handle the button press."""
        await async_sync_device_time(self._data.client, self._data.device.name)
