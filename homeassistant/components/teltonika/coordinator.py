"""DataUpdateCoordinator for Teltonika."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from teltasync import Teltasync, TeltonikaConnectionError
from teltasync.modems import Modems

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import TeltonikaConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class TeltonikaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Teltonika data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Teltasync,
        config_entry: TeltonikaConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Teltonika",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Teltonika device."""
        modems = Modems(self.client.auth)
        try:
            # Get modems data using the teltasync library
            modems_response = await modems.get_status()
        except TeltonikaConnectionError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err

        # Return only modems which are online
        modem_data = {}
        if modems_response.data:
            for modem in modems_response.data:
                if Modems.is_online(modem):
                    modem_data[modem.id] = modem

        return modem_data
