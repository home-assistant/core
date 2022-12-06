"""Bouncie data update class."""
import datetime
import logging

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
from bounciepy import AsyncRESTAPIClient
from bounciepy.exceptions import BouncieException, UnauthorizedError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN


class BouncieDataUpdateCoordinator(DataUpdateCoordinator):
    """Define Bouncie data updater."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code: str,
        session: ClientSession,
        update_interval: datetime.timedelta,
    ) -> None:
        """Init the coordinator."""
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._code = code

        self.bouncie_client = AsyncRESTAPIClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_url=redirect_uri,
            auth_code=code,
            session=session,
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
