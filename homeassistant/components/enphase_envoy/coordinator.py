"""The enphase_envoy component."""
from __future__ import annotations

import contextlib
import datetime
from datetime import timedelta
import logging
from typing import Any

from pyenphase import (
    Envoy,
    EnvoyError,
    EnvoyTokenAuth,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import CONF_TOKEN, INVALID_AUTH_ERRORS

SCAN_INTERVAL = timedelta(seconds=60)

TOKEN_REFRESH_CHECK_INTERVAL = timedelta(days=1)
STALE_TOKEN_THRESHOLD = timedelta(days=30).total_seconds()

_LOGGER = logging.getLogger(__name__)


class EnphaseUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """DataUpdateCoordinator to gather data from any envoy."""

    envoy_serial_number: str

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize DataUpdateCoordinator for the envoy."""
        entry_data = entry.data
        self.entry = entry
        self.host = entry_data[CONF_HOST]
        self.username = entry_data[CONF_USERNAME]
        self.password = entry_data[CONF_PASSWORD]
        super().__init__(
            hass,
            _LOGGER,
            name=entry_data[CONF_NAME],
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )
        envoy = self._async_make_envoy()
        self.envoy = envoy
        self._setup_complete = False
        self._cancel_token_refresh: CALLBACK_TYPE | None = None

    @callback
    def _async_make_envoy(self) -> Envoy:
        """Make a new envoy instance."""
        return Envoy(self.host, get_async_client(self.hass, verify_ssl=False))

    @callback
    def _async_refresh_token_if_needed(self, now: datetime.datetime) -> None:
        """Refresh token so we can still talk to the device if the cloud service goes offline."""
        assert isinstance(self.envoy.auth, EnvoyTokenAuth)
        expire_time = self.envoy.auth.expire_timestamp
        if (remain := expire_time - now.timestamp()) > STALE_TOKEN_THRESHOLD:
            _LOGGER.debug(
                "%s: Token is not stale (%s seconds remain), skipping refresh",
                self.name,
                remain,
            )
            return
        _LOGGER.debug("%s: Refreshing token (%s seconds remain)", self.name, remain)
        self.hass.async_create_background_task(
            self._async_try_refresh_token(), "{self.name} token refresh"
        )

    async def _async_try_refresh_token(self) -> None:
        """Try to refresh token."""
        assert isinstance(self.envoy.auth, EnvoyTokenAuth)
        _LOGGER.debug("%s: Trying to refresh token", self.name)
        try:
            await self.envoy.auth.refresh()
        except INVALID_AUTH_ERRORS as err:
            _LOGGER.debug("%s: Failed to refresh token: %s", err, self.name)
            return
        except EnvoyError as err:
            _LOGGER.debug(
                "%s: Error communicating with API to refresh token: %s", err, self.name
            )
            return
        _LOGGER.debug("%s: Token refreshed", self.name)
        self._async_update_saved_token()

    @callback
    def _async_mark_setup_complete(self) -> None:
        """Mark setup as complete and setup token refresh if needed."""
        self._setup_complete = True
        if self._cancel_token_refresh:
            self._cancel_token_refresh()
            self._cancel_token_refresh = None
        if not isinstance(self.envoy.auth, EnvoyTokenAuth):
            return
        _LOGGER.debug(
            "%s: Scheduling token refresh at interval: %s",
            self.name,
            TOKEN_REFRESH_CHECK_INTERVAL,
        )
        self._cancel_token_refresh = async_track_time_interval(
            self.hass,
            self._async_refresh_token_if_needed,
            TOKEN_REFRESH_CHECK_INTERVAL,
        )

    async def _async_setup_and_authenticate(self) -> None:
        """Set up and authenticate with the envoy."""
        envoy = self.envoy
        await envoy.setup()
        assert envoy.serial_number is not None
        self.envoy_serial_number = envoy.serial_number
        if token := self.entry.data.get(CONF_TOKEN):
            with contextlib.suppress(*INVALID_AUTH_ERRORS):
                # Always set the username and password
                # so we can refresh the token if needed
                await envoy.authenticate(
                    username=self.username, password=self.password, token=token
                )
                # The token is valid, but we still want
                # to refresh it if it's stale right away
                self._async_refresh_token_if_needed(dt_util.utcnow())
                return
            # token likely expired or firmware changed
            # so we fall through to authenticate with
            # username/password
        await self._async_authenticate_with_username_password()

    async def _async_authenticate_with_username_password(self) -> None:
        """Authenticate with username/password."""
        await self.envoy.authenticate(username=self.username, password=self.password)
        self._async_update_saved_token()

    def _async_update_saved_token(self) -> None:
        """Update saved token in config entry."""
        envoy = self.envoy
        if not isinstance(envoy.auth, EnvoyTokenAuth):
            return
        # update token in config entry so we can
        # startup without hitting the Cloud API
        # as long as the token is valid
        _LOGGER.debug("%s: Updating token in config entry from auth", self.name)
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={
                **self.entry.data,
                CONF_TOKEN: envoy.auth.token,
            },
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all device and sensor data from api."""
        envoy = self.envoy
        for tries in range(2):
            try:
                if not self._setup_complete:
                    await self._async_setup_and_authenticate()
                    self._async_mark_setup_complete()
                return (await envoy.update()).raw
            except INVALID_AUTH_ERRORS as err:
                if self._setup_complete and tries == 0:
                    # token likely expired or firmware changed, try to re-authenticate
                    self._setup_complete = False
                    continue
                raise ConfigEntryAuthFailed from err
            except EnvoyError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

        raise RuntimeError("Unreachable code in _async_update_data")  # pragma: no cover
