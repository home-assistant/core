"""Coordinator for the Panasonic Viera integration."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

if TYPE_CHECKING:
    from . import Remote

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

type PanasonicVieraConfigEntry = ConfigEntry[PanasonicVieraCoordinator]


class PanasonicVieraCoordinator(DataUpdateCoordinator[None]):
    """Poll a Panasonic Viera TV on behalf of all of its entities."""

    config_entry: PanasonicVieraConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PanasonicVieraConfigEntry,
        remote: Remote,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.remote = remote

    @override
    async def _async_update_data(self) -> None:
        """Refresh the TV state; the remote tracks its own availability."""
        await self.remote.async_update()
