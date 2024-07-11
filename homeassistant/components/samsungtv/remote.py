"""Support for the SamsungTV remote."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import ATTR_NUM_REPEATS, RemoteEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SamsungTVConfigEntry
from .const import LOGGER
from .entity import SamsungTVEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SamsungTVConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Samsung TV from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([SamsungTVRemote(coordinator=coordinator)])


class SamsungTVRemote(SamsungTVEntity, RemoteEntity):
    """Device that sends commands to a SamsungTV."""

    _attr_name = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._attr_is_on = self.coordinator.is_on
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await super()._async_turn_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to a device.

        Supported keys vary between models.
        See https://github.com/jaruba/ha-samsungtv-tizen/blob/master/Key_codes.md
        """
        if self._bridge.power_off_in_progress:
            LOGGER.info("TV is powering off, not sending keys: %s", command)
            return

        num_repeats = kwargs[ATTR_NUM_REPEATS]
        command_list = list(command)

        for _ in range(num_repeats):
            await self._bridge.async_send_keys(command_list)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the remote on."""
        await super()._async_turn_on()
