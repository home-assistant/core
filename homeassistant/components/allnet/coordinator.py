"""Data update coordinator for ALLNET."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from allnet import AllnetClient, AllnetConnectionError
from allnet.exceptions import AllnetAuthenticationError, AllnetInvalidResponseError
from allnet.models import Channel

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from . import AllnetConfigEntry

_LOGGER = logging.getLogger(__name__)


class AllnetDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Channel]]):
    """Coordinate ALLNET polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AllnetConfigEntry,
        client: AllnetClient,
    ) -> None:
        """Initialize the coordinator."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.unique_id or entry.entry_id}",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Channel]:
        """Fetch channel data from the ALLNET device."""
        try:
            channels = await self.client.async_get_channels()
        except AllnetAuthenticationError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except AllnetConnectionError as err:
            raise UpdateFailed(f"Cannot connect: {err}") from err
        except AllnetInvalidResponseError as err:
            raise UpdateFailed(f"Invalid API response: {err}") from err

        return {ch.id: ch for ch in channels}
