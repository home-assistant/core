"""Define an object to manage fetching TRMNL data."""

from datetime import timedelta
from typing import override

from trmnl import TRMNLClient
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError
from trmnl.models import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, OAUTH2_SCOPES
from .home import HomePusher

type TRMNLConfigEntry = ConfigEntry[TRMNLCoordinator]


def scope_granted(entry: TRMNLConfigEntry, scope: str) -> bool:
    """Return True if the user granted the scope on the TRMNL consent page."""
    return scope in entry.data["token"].get("scope", OAUTH2_SCOPES).split()


class TRMNLCoordinator(DataUpdateCoordinator[dict[int, Device]]):
    """Class to manage fetching TRMNL data."""

    config_entry: TRMNLConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TRMNLConfigEntry,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self.oauth_session = oauth_session
        self.home_pusher: HomePusher | None = None
        self.client = TRMNLClient(
            token=oauth_session.token["access_token"],
            session=async_get_clientsession(hass),
        )

    async def async_ensure_token_valid(self) -> None:
        """Refresh the OAuth access token when it expires."""
        await self.oauth_session.async_ensure_token_valid()
        self.client.token = self.oauth_session.token["access_token"]

    @override
    async def _async_update_data(self) -> dict[int, Device]:
        """Fetch data from TRMNL."""
        await self.async_ensure_token_valid()
        try:
            devices = await self.client.get_devices()
        except TRMNLAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from err
        except TRMNLError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err
        new_data = {device.identifier: device for device in devices}
        if self.data is not None:
            device_registry = dr.async_get(self.hass)
            for device_id in set(self.data) - set(new_data):
                if entry := device_registry.async_get_device_by_identifier(
                    (DOMAIN, str(device_id)), self.config_entry.entry_id
                ):
                    device_registry.async_remove_device(entry.id)
        return new_data
