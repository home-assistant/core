"""Support for MadVR remote control."""

from collections.abc import Iterable
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MadVRCoordinator

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import MadVRConfigEntry


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

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: MadVRCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the remote entity."""
        super().__init__(coordinator)
        self.madvr_client = coordinator.client
        self._attr_name = coordinator.device_info.get("name")
        self._attr_unique_id = f"{entry_id}_remote"
        self.connection_event = self.madvr_client.connection_event

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return self.madvr_client.is_on

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        _LOGGER.debug("Turning off")
        await self.madvr_client.power_off()
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.debug("self._state is now: %s", self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        _LOGGER.debug("Turning on device")
        # supply the stored mac to the client
        await self.madvr_client.power_on()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        _LOGGER.debug("adding command %s", command)
        await self.madvr_client.add_command_to_queue(command)
