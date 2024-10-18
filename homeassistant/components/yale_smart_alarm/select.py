"""Select for Yale Alarm."""

from __future__ import annotations

from yalesmartalarmclient import YaleLock, YaleLockVolume

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import YaleConfigEntry
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleLockEntity

VOLUME_OPTIONS = {value.name.lower(): str(value.value) for value in YaleLockVolume}


async def async_setup_entry(
    hass: HomeAssistant, entry: YaleConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale select entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        YaleLockVolumeSelect(coordinator, lock)
        for lock in coordinator.locks
        if lock.supports_lock_config()
    )


class YaleLockVolumeSelect(YaleLockEntity, SelectEntity):
    """Representation of a Yale lock volume select."""

    _attr_translation_key = "volume"

    def __init__(self, coordinator: YaleDataUpdateCoordinator, lock: YaleLock) -> None:
        """Initialize the Yale volume select."""
        super().__init__(coordinator, lock)
        self._attr_unique_id = f"{lock.sid()}-volume"
        self._attr_current_option = self.lock_data.volume().name.lower()
        self._attr_options = [volume.name.lower() for volume in YaleLockVolume]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        convert_to_value = VOLUME_OPTIONS[option]
        option_enum = YaleLockVolume(convert_to_value)
        if await self.hass.async_add_executor_job(
            self.lock_data.set_volume, option_enum
        ):
            self._attr_current_option = self.lock_data.volume().name.lower()
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_option = self.lock_data.volume().name.lower()
        super()._handle_coordinator_update()
