"""Support for madVR remote control."""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from madvr_envy.integration_bridge import iter_remote_operations, resolve_action_method

from .entity import MadvrEnvyEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the madVR remote."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([MadvrRemote(coordinator)])


class MadvrRemote(MadvrEnvyEntity, RemoteEntity):
    """Remote entity for the madVR integration."""

    _attr_name = None
    _attr_translation_key = "remote"

    def __init__(self, coordinator) -> None:  # noqa: ANN001
        """Initialize the remote entity."""
        super().__init__(coordinator, "remote")
        self._attr_unique_id = coordinator.mac

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return self.available and self.data.get("power_state") != "off"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        _LOGGER.debug("Turning off")
        await self._execute("Standby", self._client.standby)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        _LOGGER.debug("Turning on device")
        await self._execute("KeyPress POWER", lambda: self._client.key_press("POWER"))

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        _LOGGER.debug("Adding command %s", command)
        for operation in iter_remote_operations(command):
            if operation.kind == "action":
                await self._run_action(operation.value)
                continue
            key = operation.value
            await self._execute(
                f"KeyPress {key}", lambda button=key: self._client.key_press(button)
            )

    async def _run_action(self, action: str) -> None:
        try:
            command = resolve_action_method(self._client, action)
        except ValueError:
            return
        await self._execute(action.strip().lower(), command)
