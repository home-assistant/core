"""Support for MadVR remote control."""

from collections.abc import Iterable
import logging
from typing import Any

from madvr.madvr import Madvr

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MadVRCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MadVR remote."""
    coordinator: MadVRCoordinator = entry.runtime_data
    if not isinstance(coordinator, MadVRCoordinator):
        raise TypeError("entry.runtime_data is not an instance of MadVRCoordinator")

    madvr_client = coordinator.client

    async_add_entities(
        [
            MadvrRemote(hass, coordinator, madvr_client, entry.entry_id),
        ]
    )


class MadvrRemote(CoordinatorEntity, RemoteEntity):
    """Remote entity for the MadVR integration."""

    coordinator: MadVRCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: MadVRCoordinator,
        madvr_client: Madvr,
        entry_id: str,
    ) -> None:
        """Initialize the remote entity."""
        super().__init__(coordinator)
        self.madvr_client = madvr_client
        self.coordinator = coordinator
        self._attr_name = coordinator.name
        self._attr_unique_id = f"{entry_id}_remote"
        self.entry_id = entry_id
        self._attr_should_poll = False
        self.connection_event = self.madvr_client.connection_event

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug("Adding to hass")

    async def async_will_remove_from_hass(self) -> None:
        """Run when removed."""
        _LOGGER.debug("Removing from hass")

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
        # power state will be captured once the connection is established
        await self.madvr_client.power_on()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        _LOGGER.debug("adding command %s", command)
        await self.madvr_client.add_command_to_queue(command)
