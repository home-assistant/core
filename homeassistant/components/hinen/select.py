"""Support for Hinen Sensors."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    AUTH,
    COORDINATOR,
    DOMAIN,
    WORK_MODE_NONE,
    WORK_MODE_OPTIONS,
    WORK_MODE_SETTING,
)
from .coordinator import HinenDataUpdateCoordinator
from .entity import HinenDeviceEntity
from .hinen import HinenOpen

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=False)
class HinenSelectEntityDescription(SelectEntityDescription):
    """Describes Hinen select entity."""


SELECT_TYPES = [
    HinenSelectEntityDescription(
        key=WORK_MODE_SETTING,
        translation_key=WORK_MODE_SETTING,
        options=list(WORK_MODE_OPTIONS.values()),
        entity_category=EntityCategory.CONFIG,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hinen select."""
    coordinator: HinenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    hinen_open: HinenOpen = hass.data[DOMAIN][entry.entry_id][AUTH].hinen_open

    entities: list = [
        HinenWorkModeSelect(coordinator, hinen_open, sensor_type, device_id)
        for device_id in coordinator.data
        for sensor_type in SELECT_TYPES
    ]

    async_add_entities(entities)


class HinenWorkModeSelect(HinenDeviceEntity, SelectEntity):
    """Hinen work mode select."""

    entity_description: HinenSelectEntityDescription

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return True

    @property
    def current_option(self) -> str | None:
        """Return the current work mode."""
        if not self.coordinator.data:
            return None
        mode = self.coordinator.data[self._device_id][WORK_MODE_SETTING]
        _LOGGER.debug("current mode_value: %s", mode)
        return WORK_MODE_OPTIONS.get(mode, WORK_MODE_OPTIONS[WORK_MODE_NONE])

    async def async_select_option(self, option: str) -> None:
        """Change the work mode."""
        mode_value = None
        for key, value in WORK_MODE_OPTIONS.items():
            if value == option:
                mode_value = key
                break
        _LOGGER.debug("mode_value: %s", mode_value)
        if mode_value is not None:
            await self.hinen_open.set_device_work_mode(mode_value, self._device_id)
            self.coordinator.data[self._device_id][WORK_MODE_SETTING] = mode_value
            self.async_write_ha_state()
