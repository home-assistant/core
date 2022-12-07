"""Bouncie data update class."""
import datetime
import logging

from aiohttp.client_exceptions import ClientConnectorError
from bounciepy import AsyncRESTAPIClient
from bounciepy.exceptions import BouncieException, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CODE, CONF_REDIRECT_URI, DOMAIN


class BouncieDataUpdateCoordinator(DataUpdateCoordinator):
    """Define Bouncie data updater."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        config_entry: ConfigEntry,
        update_interval: datetime.timedelta,
    ) -> None:
        """Init the coordinator."""
        self._client_id = config_entry.data[CONF_CLIENT_ID]
        self.bouncie_client = AsyncRESTAPIClient(
            client_id=config_entry.data[CONF_CLIENT_ID],
            client_secret=config_entry.data[CONF_CLIENT_SECRET],
            redirect_url=config_entry.data[CONF_REDIRECT_URI],
            auth_code=config_entry.data[CONF_CODE],
            session=async_get_clientsession(hass=hass),
        )

        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        data = {}
        all_vehicles = None
        try:
            all_vehicles = await self.bouncie_client.get_all_vehicles()
        except (UnauthorizedError):
            try:
                if True is await self.bouncie_client.get_access_token():
                    all_vehicles = await self.bouncie_client.get_all_vehicles()
            except (BouncieException, ClientConnectorError) as error:
                raise UpdateFailed(error) from error
        data["vehicles"] = all_vehicles
        return data
