"""Support for madVR remote control."""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MadVRConfigEntry, MadVRCoordinator
from .entity import MadVREntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MadVRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the madVR remote."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            MadvrRemote(coordinator),
        ]
    )


class MadvrRemote(MadVREntity, RemoteEntity):
    """Remote entity for the madVR integration."""

    _attr_name = None

    def __init__(
        self,
        coordinator: MadVRCoordinator,
    ) -> None:
        """Initialize the remote entity."""
        super().__init__(coordinator)
        self.madvr_client = coordinator.client
        self._attr_unique_id = coordinator.mac

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return self.madvr_client.is_on

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        _LOGGER.debug("Turning off")
        try:
            await self.madvr_client.power_off()
        except (ConnectionError, NotImplementedError) as err:
            _LOGGER.error("Failed to turn off device %s", err)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        _LOGGER.debug("Turning on device")

        try:
            await self.madvr_client.power_on(mac=self.coordinator.mac)
        except (ConnectionError, NotImplementedError) as err:
            _LOGGER.error("Failed to turn on device %s", err)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        _LOGGER.debug("adding command %s", command)
        try:
            await self.madvr_client.add_command_to_queue(command)
        except (ConnectionError, NotImplementedError) as err:
            _LOGGER.error("Failed to send command %s", err)
