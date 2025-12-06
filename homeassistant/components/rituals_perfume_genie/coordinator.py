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
        except (AuthenticationException, ClientResponseError) as err:
            # Treat 401/403 like AuthenticationException → one silent re-auth, single retry
            if isinstance(err, ClientResponseError) and (status := err.status) not in (
                401,
                403,
            ):
                # Non-auth HTTP error → let HA retry
                raise UpdateFailed(f"HTTP {status}") from err

            self.logger.debug(
                "Auth issue detected (%r). Attempting silent re-auth.", err
            )
            try:
                await self.account.authenticate()
                await self.diffuser.update_data()
            except AuthenticationException as err2:
                # Credentials invalid → trigger HA reauth
                raise ConfigEntryAuthFailed from err2
            except ClientResponseError as err2:
                # Still HTTP auth errors after refresh → trigger HA reauth
                if err2.status in (401, 403):
                    raise ConfigEntryAuthFailed from err2
                raise UpdateFailed(f"HTTP {err2.status}") from err2
        except ClientError as err:
            # Network issues (timeouts, DNS, etc.)
            raise UpdateFailed(f"Network error: {err!r}") from err
