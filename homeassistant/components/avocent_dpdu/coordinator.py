"""DataUpdateCoordinator for Avocent DPDU."""

from datetime import timedelta
from typing import Any

from avocentdpdu.avocentdpdu import AvocentDPDU

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


class AvocentDpduDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Avocent DPDU data from single endpoint."""

    _connected: bool = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            # Don't refresh immediately, give the device time to process
            # the change in state before we query it.
            request_refresh_debouncer=Debouncer(
                hass,
                LOGGER,
                cooldown=1.5,
                immediate=False,
            ),
        )

        self.api = AvocentDPDU(
            host=entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            timeout=10,
        )

    async def _connect(self) -> None:
        """Connect to the Avocent DPDU."""
        LOGGER.debug("Initialize coordinator")
        await self.api.initialize()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from PDU."""
        LOGGER.debug("Update data request")
        await self.api.update()
        return {}
