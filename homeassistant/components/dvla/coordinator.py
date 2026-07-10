"""DVLA Coordinator."""

from datetime import timedelta
import logging
from typing import Any, override

from aio_dvla_vehicle_enquiry import DVLAClient, DVLAError
from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_KEY

_LOGGER = logging.getLogger(__name__)


class DVLACoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry | None,
        session: ClientSession,
        reg_number: str,
    ) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title if config_entry else "DVLA",
            update_interval=timedelta(days=1),
        )
        self.session = session
        self.reg_number = str(reg_number).replace(" ", "").upper()

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch vehicle data from the DVLA API."""
        client = DVLAClient(self.session, API_KEY)

        try:
            return await client.async_get_vehicle(self.reg_number)
        except DVLAError as err:
            raise UpdateFailed(str(err)) from err
