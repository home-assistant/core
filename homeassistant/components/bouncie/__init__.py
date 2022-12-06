"""The bouncie integration."""
from __future__ import annotations

import datetime
import logging

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
from bounciepy import AsyncRESTAPIClient
from bounciepy.exceptions import BouncieException, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bouncie from a config entry."""

    update_interval = datetime.timedelta(seconds=60)
    session = async_get_clientsession(hass=hass)
    coordinator = BouncieDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        client_id=entry.data["client_id"],
        client_secret=entry.data["client_secret"],
        redirect_uri=entry.data["redirect_uri"],
        code=entry.data["code"],
        session=session,
        update_interval=update_interval,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


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
        # return await super()._async_update_data()
