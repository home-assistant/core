"""Coordinator for BMW."""
from __future__ import annotations

from datetime import timedelta
import logging

from bimmer_connected.account import MyBMWAccount
from bimmer_connected.api.regions import get_region_from_name
from bimmer_connected.models import GPSPosition, MyBMWAPIError, MyBMWAuthError
from httpx import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_READ_ONLY, CONF_REFRESH_TOKEN, DOMAIN

DEFAULT_SCAN_INTERVAL_SECONDS = 300
SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)
_LOGGER = logging.getLogger(__name__)


class BMWDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching BMW data."""

    account: MyBMWAccount

    def __init__(self, hass: HomeAssistant, *, entry: ConfigEntry) -> None:
        """Initialize account-wide BMW data updater."""
        self.account = MyBMWAccount(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            get_region_from_name(entry.data[CONF_REGION]),
            observer_position=GPSPosition(hass.config.latitude, hass.config.longitude),
            # Force metric system as BMW API apparently only returns metric values now
            use_metric_units=True,
        )
        self.read_only = entry.options[CONF_READ_ONLY]
        self._entry = entry

        if CONF_REFRESH_TOKEN in entry.data:
            self.account.set_refresh_token(entry.data[CONF_REFRESH_TOKEN])

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry.data['username']}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from BMW."""
        old_refresh_token = self.account.refresh_token

        try:
            await self.account.get_vehicles()
        except MyBMWAuthError as err:
            # Clear refresh token and trigger reauth
            self._update_config_entry_refresh_token(None)
            raise ConfigEntryAuthFailed(str(err)) from err

        except (MyBMWAPIError, RequestError) as err:
            if self.last_update_success is True:
                _LOGGER.warning(
                    "Error communicating with BMW API (%s): %s",
                    type(err).__name__,
                    err,
                )
                self.last_update_success = False

        if self.account.refresh_token != old_refresh_token:
            self._update_config_entry_refresh_token(self.account.refresh_token)
            _LOGGER.debug(
                "bimmer_connected: refresh token %s > %s",
                old_refresh_token,
                self.account.refresh_token,
            )

        if self.last_update_success is False:
            _LOGGER.info("Reconnected to BMW API")

    def _update_config_entry_refresh_token(self, refresh_token: str | None) -> None:
        """Update or delete the refresh_token in the Config Entry."""
        data = {
            **self._entry.data,
            CONF_REFRESH_TOKEN: refresh_token,
        }
        if not refresh_token:
            data.pop(CONF_REFRESH_TOKEN)
        self.hass.config_entries.async_update_entry(self._entry, data=data)
