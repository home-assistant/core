"""Data update coordinator for the JVC Projector integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from jvcprojector import JvcProjector, JvcProjectorAuthError, JvcProjectorConnectError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 15


class JvcProjectorDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the JVC Projector integration."""

    def __init__(self, hass: HomeAssistant, device: JvcProjector) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=const.NAME,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self._device = device

    @property
    def device(self) -> JvcProjector:
        """Return the device representing the projector."""
        return self._device

    async def _async_update_data(self) -> dict[str, str]:
        """Get the latest state data."""
        try:
            state = await self._device.get_state()
        except JvcProjectorConnectError as err:
            raise UpdateFailed("Connection error occurred") from err
        except JvcProjectorAuthError as err:
            raise ConfigEntryAuthFailed("Password auth failed") from err

        return state
