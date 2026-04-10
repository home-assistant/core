"""Remote platform for Vizio SmartCast devices."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VizioConfigEntry, VizioDeviceCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VizioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Vizio remote entity."""
    async_add_entities([VizioRemote(config_entry)])


class VizioRemote(CoordinatorEntity[VizioDeviceCoordinator], RemoteEntity):
    """Remote entity for Vizio SmartCast devices."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: VizioConfigEntry) -> None:
        """Initialize the remote entity."""
        coordinator = config_entry.runtime_data.device_coordinator
        super().__init__(coordinator)
        self._attr_unique_id = unique_id = config_entry.unique_id
        # Guard against config entries missing unique_id, which should never happen
        if TYPE_CHECKING:
            assert unique_id is not None
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})
        self._device = coordinator.device
        valid_keys = set(self._device.get_remote_keys_list())
        self._command_map: dict[str, str] = {key.lower(): key for key in valid_keys}

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.coordinator.data.is_on

    def _resolve_command(self, command: str) -> str:
        """Resolve an lowercased command string to a pyvizio key name."""
        if resolved := self._command_map.get(command):
            return resolved
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_command",
            translation_placeholders={"command": command},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        await self._device.pow_on(log_api_exception=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self._device.pow_off(log_api_exception=False)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send remote commands to the device."""
        num_repeats: int = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay: float = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        resolved = [vol.All(vol.Lower, self._resolve_command)(cmd) for cmd in command]

        for i in range(num_repeats):
            for cmd in resolved:
                await self._device.remote(cmd, log_api_exception=False)
            if i < num_repeats - 1:
                await asyncio.sleep(delay)
