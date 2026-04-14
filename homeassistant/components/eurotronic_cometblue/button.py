"""Comet Blue button platform."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import CometBlueConfigEntry, CometBlueDataUpdateCoordinator
from .entity import CometBlueBluetoothEntity

PARALLEL_UPDATES = 1

DESCRIPTIONS = [
    ButtonEntityDescription(
        key="sync_time",
        translation_key="sync_time",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CometBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the client entities."""

    coordinator = entry.runtime_data

    async_add_entities(
        [
            CometBlueButtonEntity(coordinator, description)
            for description in DESCRIPTIONS
        ]
    )


class CometBlueButtonEntity(CometBlueBluetoothEntity, ButtonEntity):
    """Representation of a button."""

    def __init__(
        self,
        coordinator: CometBlueDataUpdateCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize CometBlueButtonEntity."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}-{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.key == "sync_time":
            await self.coordinator.send_command(
                self.coordinator.device.set_datetime_async, {"date": dt_util.now()}
            )
