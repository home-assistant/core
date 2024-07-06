"""Support for MadVR remote control."""

from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MadVRConfigEntry
from .const import DOMAIN
from .coordinator import MadVRCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MadVRConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MadVR remote."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            MadvrRemote(hass, coordinator, entry.entry_id),
        ]
    )


class MadvrRemote(CoordinatorEntity[MadVRCoordinator], RemoteEntity):
    """Remote entity for the MadVR integration."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: MadVRCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the remote entity."""
        super().__init__(coordinator)
        self.madvr_client = coordinator.client
        self._attr_unique_id = coordinator.mac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.mac}")},
            name="madVR Envy",
            manufacturer="madVR",
            model="Envy",
        )

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
