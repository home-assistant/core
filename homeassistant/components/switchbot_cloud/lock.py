"""Support for the Switchbot lock."""

from typing import Any

from switchbot_api import LockCommands

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_SW_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .entity import SwitchBotCloudEntity

ATTR_CALIBRATED = "calibrated"
ATTR_DOOR_STATE = "door_state"


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        SwitchBotCloudLock(data.api, device, coordinator)
        for device, coordinator in data.devices.locks
    )


class SwitchBotCloudLock(SwitchBotCloudEntity, LockEntity):
    """Representation of a SwitchBot lock."""

    _sw_version: str | None = None
    _battery_level = -1
    _calibrated: bool | None = None
    _door_state: str | None = None
    _attr_name = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if coord_data := self.coordinator.data:
            self._attr_is_locked = coord_data["lockState"] == "locked"
            self._attr_is_locking = coord_data["lockState"] == "locking"
            self._attr_is_unlocking = coord_data["lockState"] == "unlocking"
            self._attr_is_jammed = coord_data["lockState"] == "jammed"
            self._battery_level = coord_data["battery"]
            self._sw_version = coord_data["version"]
            self._calibrated = coord_data["calibrate"]
            self._door_state = coord_data["doorState"]
            self.async_write_ha_state()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self.send_api_command(LockCommands.LOCK)
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""

        await self.send_api_command(LockCommands.UNLOCK)
        self._attr_is_locked = False
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            ATTR_SW_VERSION: self._sw_version,
            ATTR_BATTERY_LEVEL: self._battery_level,
            ATTR_CALIBRATED: self._calibrated,
            ATTR_DOOR_STATE: self._door_state,
        }
