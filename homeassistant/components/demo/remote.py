"""Demo platform that has two fake remotes."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    async_add_entities(
        [
            DemoRemote("Remote One", False),
            DemoRemote("Remote Two", True),
        ]
    )


class DemoRemote(RemoteEntity):
    """Representation of a demo remote."""

    _attr_should_poll = False

    def __init__(self, name: str | None, state: bool) -> None:
        """Initialize the Demo Remote."""
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_is_on = state
        self._last_command_sent: str | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device state attributes."""
        if self._last_command_sent is not None:
            return {"last_command_sent": self._last_command_sent}
        return None

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the remote on."""
        self._attr_is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the remote off."""
        self._attr_is_on = False
        self.schedule_update_ha_state()

    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to a device."""
        for com in command:
            self._last_command_sent = com
        self.schedule_update_ha_state()
