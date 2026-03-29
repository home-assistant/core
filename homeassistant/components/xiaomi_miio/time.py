"""Support for Xiaomi Miio time entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any

from miio import Device as MiioDevice

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import CONF_MODEL, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import MODEL_PET_FOUNTAIN_70M2
from .entity import XiaomiCoordinatedMiioEntity
from .typing import XiaomiMiioConfigEntry

ATTR_DND_START = "dnd_start"
ATTR_DND_END = "dnd_end"


@dataclass(frozen=True, kw_only=True)
class XiaomiMiioTimeDescription(TimeEntityDescription):
    """A class that describes Xiaomi Miio time entities."""

    method: str
    set_error_message: str


TIME_TYPES = (
    XiaomiMiioTimeDescription(
        key=ATTR_DND_START,
        translation_key=ATTR_DND_START,
        icon="mdi:clock-start",
        method="set_dnd_start",
        set_error_message=(
            "Setting the do not disturb start time of the miio device failed."
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioTimeDescription(
        key=ATTR_DND_END,
        translation_key=ATTR_DND_END,
        icon="mdi:clock-end",
        method="set_dnd_end",
        set_error_message=(
            "Setting the do not disturb end time of the miio device failed."
        ),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: XiaomiMiioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xiaomi Miio time entities."""
    if config_entry.data[CONF_MODEL] != MODEL_PET_FOUNTAIN_70M2:
        return

    device = config_entry.runtime_data.device
    coordinator = config_entry.runtime_data.device_coordinator
    unique_id = config_entry.unique_id

    async_add_entities(
        XiaomiMiioTimeEntity(
            device,
            config_entry,
            f"{description.key}_{unique_id}",
            coordinator,
            description,
        )
        for description in TIME_TYPES
    )


class XiaomiMiioTimeEntity(
    XiaomiCoordinatedMiioEntity[DataUpdateCoordinator[Any]], TimeEntity
):
    """Representation of a Xiaomi Miio time entity."""

    entity_description: XiaomiMiioTimeDescription

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str,
        coordinator: DataUpdateCoordinator[Any],
        description: XiaomiMiioTimeDescription,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(device, entry, unique_id, coordinator)
        self.entity_description = description
        self._attr_native_value = self._extract_native_value()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update from the coordinator."""
        self._attr_native_value = self._extract_native_value()
        self.async_write_ha_state()

    def _extract_native_value(self) -> time | None:
        """Return the time value from coordinator data."""
        return getattr(self.coordinator.data, self.entity_description.key, None)

    async def async_set_value(self, value: time) -> None:
        """Set the time value."""
        method = getattr(self._device, self.entity_description.method)
        if await self._try_command(
            self.entity_description.set_error_message,
            method,
            value,
        ):
            self._attr_native_value = value
            self.async_write_ha_state()
