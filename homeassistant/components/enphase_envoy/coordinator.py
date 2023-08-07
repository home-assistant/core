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
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
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

    def __init__(self, hass: HomeAssistant, envoy: Envoy, entry: ConfigEntry) -> None:
        """Initialize DataUpdateCoordinator for the envoy."""
        self.envoy = envoy
        entry_data = entry.data
        self.entry = entry
        self.username = entry_data[CONF_USERNAME]
        self.password = entry_data[CONF_PASSWORD]
        self._setup_complete = False
        self._cancel_token_refresh: CALLBACK_TYPE | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=entry_data[CONF_NAME],
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )

    @callback
    def _async_refresh_token_if_needed(self, now: datetime.datetime) -> None:
        """Proactively refresh token if its stale in case cloud services goes down."""
        assert isinstance(self.envoy.auth, EnvoyTokenAuth)
        expire_time = self.envoy.auth.expire_timestamp
        remain = expire_time - now.timestamp()
        fresh = remain > STALE_TOKEN_THRESHOLD
        name = self.name
        _LOGGER.debug("%s: %s seconds remaining on token fresh=%s", name, remain, fresh)
        if not fresh:
            self.hass.async_create_background_task(
                self._async_try_refresh_token(), "{name} token refresh"
            )

    async def _async_try_refresh_token(self) -> None:
        """Try to refresh token."""
        assert isinstance(self.envoy.auth, EnvoyTokenAuth)
        _LOGGER.debug("%s: Trying to refresh token", self.name)
        try:
            await self.envoy.auth.refresh()
        except EnvoyError as err:
            # If we can't refresh the token, we try again later
            # If the token actually ends up expiring, we'll
            # re-authenticate with username/password and get a new token
            # or log an error if that fails
            _LOGGER.debug("%s: Error refreshing token: %s", err, self.name)
            return
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
        self._cancel_token_refresh = async_track_time_interval(
            self.hass,
            self._async_refresh_token_if_needed,
            TOKEN_REFRESH_CHECK_INTERVAL,
            cancel_on_shutdown=True,
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
        await self.envoy.authenticate(username=self.username, password=self.password)
        # Password auth succeeded, so we can update the token
        # if we are using EnvoyTokenAuth
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
