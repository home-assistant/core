"""The Rituals Perfume Genie data update coordinator."""

from datetime import timedelta
import logging

from aiohttp import ClientError, ClientResponseError
from pyrituals import Account, AuthenticationException, Diffuser

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RitualsDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Rituals Perfume Genie device data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        account: Account,
        diffuser: Diffuser,
        update_interval: timedelta,
    ) -> None:
        """Initialize global Rituals Perfume Genie data updater."""
        self.account = account
        self.diffuser = diffuser
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{diffuser.hublot}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from Rituals, with one silent re-auth on 401.

        If silent re-auth also fails, raise ConfigEntryAuthFailed to trigger reauth flow.
        Other HTTP/network errors are wrapped in UpdateFailed so HA can retry.
        """
        try:
            await self.diffuser.update_data()
        except AuthenticationException:
            # Session likely expired; try to re-authenticate once, then retry.
            try:
                await self.account.authenticate()
                await self.diffuser.update_data()
            except AuthenticationException as err2:
                raise ConfigEntryAuthFailed from err2
        except ClientResponseError as err:
            # HTTP errors (e.g., 429/5xx)
            raise UpdateFailed(f"HTTP {getattr(err, 'status', '?')}") from err
        except ClientError as err:
            # Network issues (timeouts, DNS, etc.)
            raise UpdateFailed(f"Network error: {err!r}") from err
        except Exception as err:
            # Unexpected errors
            raise UpdateFailed(str(err)) from err
