"""Support for the SamsungTV remote."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import ATTR_NUM_REPEATS, RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .entity import SamsungTVEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Samsung TV from a config entry."""
    bridge = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SamsungTVRemote(bridge=bridge, config_entry=entry)])


class SamsungTVRemote(SamsungTVEntity, RemoteEntity):
    """Device that sends commands to a SamsungTV."""

    _attr_name = None
    _attr_should_poll = False

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._bridge.async_power_off()

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
