"""Support for Hinen Sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    COORDINATOR,
    DOMAIN,
    WORK_MODE_NONE,
    WORK_MODE_OPTIONS,
    WORK_MODE_SELF_CONSUMPTION,
)
from .coordinator import HinenDataUpdateCoordinator
from .entity import HinenDeviceEntity


@dataclass(frozen=True, kw_only=False)
class HinenSelectEntityDescription(SelectEntityDescription):
    """Describes Hinen select entity."""


SELECT_TYPES = [
    HinenSelectEntityDescription(
        key="work_mode",
        translation_key="work_mode",
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
    # hinen_open: HinenOpen = hass.data[DOMAIN][entry.entry_id][AUTH].hinen_open
    entities: list = [
        HinenWorkModeSelect(coordinator, sensor_type, device_id)
        for device_id in coordinator.data
        for sensor_type in SELECT_TYPES
    ]

    async_add_entities(entities)


class HinenWorkModeSelect(HinenDeviceEntity, SelectEntity):
    """工作模式选择器."""

    entity_description: HinenSelectEntityDescription

    _attr_current_option = "1"

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return True

    @property
    def current_option(self) -> str | None:
        """Return the current work mode."""
        if not self.coordinator.data:
            return None
        # 暂时手动造数据
        # self.coordinator.data[]
        mode = WORK_MODE_SELF_CONSUMPTION
        return WORK_MODE_OPTIONS.get(mode, WORK_MODE_OPTIONS[WORK_MODE_NONE])

    async def async_select_option(self, option: str) -> None:
        """Change the work mode."""
        mode_value = None
        for key, value in WORK_MODE_OPTIONS.items():
            if value == option:
                mode_value = key
                break

        if mode_value is not None:
            # 暂时不请求后端更新
            # await self.hass.data[DOMAIN][self._device_id][COORDINATOR](mode_value)
            await self.coordinator.async_request_refresh()
