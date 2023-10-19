"""Idasen Desk switch to turn bluetooth connection on/off."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, STATE_OFF
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DeskData, IdasenDeskCoordinator
from .const import DOMAIN

RECONNECT_RETRY_SECONDS = 30

# Initialize the logger
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the cover platform for Idasen Desk."""
    data: DeskData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [IdasenDeskSwitch(data.address, data.device_info, data.coordinator)]
    )


class IdasenDeskSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Idasen Desk connection switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        address: str,
        device_info: DeviceInfo,
        coordinator: IdasenDeskCoordinator,
    ) -> None:
        """Initialize the connection switch."""
        super().__init__(coordinator)
        self._address = address
        self._attr_name = f"{device_info.get(ATTR_NAME)} Connection"
        self._attr_unique_id = address
        self._attr_device_info = device_info
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == STATE_OFF:
            await self.async_turn_off()
        else:
            # If last state is None it should also turn on, since it should be
            # on by default unless the user has explicitly turned it off.
            await self.async_turn_on()

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if not self.is_on:
            return "mdi:bluetooth-off"
        if self.coordinator.desk.is_connected:
            return "mdi:bluetooth-connect"
        return "mdi:bluetooth"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn connection on."""
        _LOGGER.debug("Turn Idasen Desk connection on %s", self._address)
        if await self.coordinator.async_connect():
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn connection off."""
        _LOGGER.debug("Turn Idasen Desk connection off %s", self._address)
        self._attr_is_on = False
        await self.coordinator.async_disconnect()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self, *args: Any) -> None:
        """Handle data update."""
        self.async_write_ha_state()
