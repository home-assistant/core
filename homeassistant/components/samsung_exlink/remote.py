"""Remote platform for the Samsung ExLink integration."""

import asyncio
from collections.abc import Iterable
from typing import Any, override

from samsung_exlink import Key, TVState

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SamsungExLinkConfigEntry, SamsungExLinkCoordinator
from .helpers import catch_command_errors

PARALLEL_UPDATES = 1
KEY_MAP = {key.name: key for key in Key if key is not Key.KEY_FACTORY}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SamsungExLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Samsung ExLink remote."""
    async_add_entities([SamsungExLinkRemote(config_entry)])


class SamsungExLinkRemote(CoordinatorEntity[SamsungExLinkCoordinator], RemoteEntity):
    """Representation of a Samsung TV remote controlled over ExLink."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, config_entry: SamsungExLinkConfigEntry) -> None:
        """Initialize the remote."""
        coordinator = config_entry.runtime_data
        super().__init__(coordinator)
        self._tv = coordinator.tv
        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Samsung",
            model=self._tv.model.name if self._tv.model else None,
        )
        self._async_update_from_state(self.coordinator.data)

    @property
    @override
    def available(self) -> bool:
        """Return if the TV has a state and coordinator updates are successful."""
        return super().available and self.coordinator.data is not None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle a coordinator state update."""
        self._async_update_from_state(self.coordinator.data)
        self.async_write_ha_state()

    @callback
    def _async_update_from_state(self, state: TVState | None) -> None:
        """Update entity state from a TV state snapshot."""
        if state is not None:
            self._attr_is_on = state.power

    @catch_command_errors
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the TV on."""
        await self._tv.power_on()

    @catch_command_errors
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the TV off."""
        await self._tv.power_off()

    @catch_command_errors
    @override
    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send one or more remote key commands to the TV."""
        keys = []
        for name in command:
            if name not in KEY_MAP:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_key",
                    translation_placeholders={"key": name},
                )
            keys.append(KEY_MAP[name])

        delay_secs = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        first_command = True
        for _ in range(kwargs[ATTR_NUM_REPEATS]):
            for key in keys:
                if not first_command:
                    await asyncio.sleep(delay_secs)
                await self._tv.send_key(key)
                first_command = False
