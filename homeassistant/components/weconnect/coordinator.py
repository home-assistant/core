"""Coordinator for WeConnect."""

import logging

from weconnect.errors import APIError, AuthentificationError
from weconnect.weconnect import Vehicle, WeConnect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SPIN, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class WeConnectCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching data from WeConnect."""

    weconnect: WeConnect

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the WeConnect coordinator."""
        self.weconnect = WeConnect(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            spin=config_entry.data[CONF_SPIN],
            loginOnInit=False,
            updateAfterLogin=False,
        )

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> None:  # type: ignore[override]
        """Fetch data from WeConnect."""
        if not self.weconnect.session.authorized:
            try:
                await self.hass.async_add_executor_job(self.weconnect.login)
            except AuthentificationError as err:
                raise ConfigEntryAuthFailed(err) from err
            except APIError as err:
                raise ConfigEntryNotReady(err) from err

        try:
            await self.hass.async_add_executor_job(self.weconnect.update)
        except Exception as err:
            raise UpdateFailed(err) from err

    @property
    def vehicles(self) -> list[Vehicle]:
        """Return a list of vehicles."""
        return self.weconnect.vehicles.values()  # type: ignore[no-any-return]
