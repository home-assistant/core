"""DataUpdateCoordinator for Teltonika."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from teltasync import Teltasync, TeltonikaConnectionError
from teltasync.modems import Modems

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class TeltonikaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Teltonika data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Teltasync,
        config_entry: ConfigEntry,
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
        try:
            # Get modems data using the teltasync library
            modems = Modems(self.client.auth)
            modems_response = await modems.get_status()

            # Return only modems which are online
            modem_data = {}
            if modems_response.data:
                for modem in modems_response.data:
                    if Modems.is_online(modem):
                        modem_data[modem.id] = modem

        except TeltonikaConnectionError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err
        else:
            return modem_data
