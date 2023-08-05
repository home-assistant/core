"""The enphase_envoy component."""
from __future__ import annotations

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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TOKEN, INVALID_AUTH_ERRORS

SCAN_INTERVAL = timedelta(seconds=60)
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
        super().__init__(
            hass,
            _LOGGER,
            name=entry_data[CONF_NAME],
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )

    async def _async_setup_and_authenticate(self) -> None:
        """Set up and authenticate with the envoy."""
        envoy = self.envoy
        await envoy.setup()
        assert envoy.serial_number is not None
        self.envoy_serial_number = envoy.serial_number

        if token := self.entry.data.get(CONF_TOKEN):
            try:
                await envoy.authenticate(token=token)
            except INVALID_AUTH_ERRORS:
                # token likely expired or firmware changed
                pass
            else:
                self._setup_complete = True
                return

        await envoy.authenticate(username=self.username, password=self.password)
        assert envoy.auth is not None

        if isinstance(envoy.auth, EnvoyTokenAuth):
            # update token in config entry so we can
            # startup without hitting the Cloud API
            # as long as the token is valid
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={
                    **self.entry.data,
                    CONF_TOKEN: envoy.auth.token,
                },
            )
        self._setup_complete = True

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all device and sensor data from api."""
        envoy = self.envoy
        for tries in range(2):
            try:
                if not self._setup_complete:
                    await self._async_setup_and_authenticate()
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
