"""Data update coordinator for the jvc_projector integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from jvcprojector import JvcProjectorAuthError, JvcProjectorConnectError

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const

if TYPE_CHECKING:
    from jvcprojector import JvcProjector

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

INTERVAL_SLOW = timedelta(seconds=15)
INTERVAL_FAST = timedelta(seconds=5)


class JvcProjectorDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the JVC Projector integration."""

    def __init__(self, hass: HomeAssistant, device: JvcProjector) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=const.NAME,
            update_interval=INTERVAL_SLOW,
        )

        self.device = device
        self.unique_id = format_mac(device.mac)

    async def _async_update_data(self) -> dict[str, str]:
        """Get the latest state data."""
        try:
            state = await self.device.get_state()
        except JvcProjectorConnectError as err:
            raise UpdateFailed("Connection error occurred") from err
        except JvcProjectorAuthError as err:
            raise ConfigEntryAuthFailed("Password auth failed") from err

        if state[const.POWER] == const.POWER_STANDBY:
            self.update_interval = INTERVAL_SLOW
        else:
            self.update_interval = INTERVAL_FAST

        return state
