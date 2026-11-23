"""Coordinator for the Theben Conexa Smartmeter gateway integration."""

from asyncio import Lock, sleep as async_sleep
from datetime import datetime
import logging
from typing import override

import aiohttp
from theben_conexa_smgw import ConexaSMGW, ConexaSmgwErr, checkNetworkConnection

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_QUERY_LOCKS

_LOGGER = logging.getLogger(__name__)

type ThebenConfigEntry = ConfigEntry[SmgwSensorCoordinator]


class SmgwSensorCoordinator(DataUpdateCoordinator[dict[str, ConexaSMGW.MeterValue]]):
    """The data update coordinator for the Theben Conexa Smartmeter gateway integration."""

    _api: ConexaSMGW
    gateway_info: ConexaSMGW.GatewayInfo
    config_entry: ThebenConfigEntry
    smgw_user: str

    def __init__(self, hass: HomeAssistant, entry: ThebenConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Theben Conexa Local Poll",
            config_entry=entry,
            # Set to None so HA doesn't poll on a standard rolling interval
            update_interval=None,
            always_update=False,
        )
        self._scheduled_updates: CALLBACK_TYPE | None = None
        self.smgw_user = entry.data[CONF_USERNAME]
        # The Conexa SMGW is not able to handle multiple concurrent requests
        # so we need a host specific lock to serialize the requests.
        # This lock pool is shared across config entries, so it cannot use runtime_data.
        self._query_lock = hass.data.setdefault(DATA_QUERY_LOCKS, {}).setdefault(
            entry.data[CONF_HOST], Lock()
        )

    async def async_init(self) -> None:
        """Asynchronous Initialization and registering the update schedule."""

        async with self._query_lock:
            try:
                await checkNetworkConnection(self.config_entry.data[CONF_HOST])
            except (TimeoutError, ConnectionRefusedError, OSError) as e:
                raise ConfigEntryNotReady("Device is not reachable") from e

            # Unfortunately the Conexa 3.0 doesn't provide separate authentication feedback it just ignores
            # all requests with invalid username/password, That's why here we need to assume it failed
            # because of wrong credentials, as we checked for connectivity just before and the device was reachable.
            try:
                self._api = await ConexaSMGW.create(
                    async_get_clientsession(self.hass),
                    self.config_entry.data[CONF_HOST],
                    self.config_entry.data[CONF_USERNAME],
                    self.config_entry.data[CONF_PASSWORD],
                )
            except (TimeoutError, aiohttp.ClientError) as e:
                raise ConfigEntryAuthFailed("Authentication failed") from e
            except ConexaSmgwErr as e:
                raise ConfigEntryNotReady(f"Unexpected reply from gateway: {e}") from e

        self.gateway_info = self._api.gatewayInfo

        # Currently the SMGW provides new data only every 15 minutes at the starting of the hour (in UTC).
        # So we leverage this information to set up a scheduled poll at
        # exactly these times + some seconds to allow for processing.
        self._scheduled_updates = async_track_utc_time_change(
            self.hass,
            self._scheduled_update,
            minute=[0, 15, 30, 45],
            second=40,
        )

    @override
    async def _async_update_data(self) -> dict[str, ConexaSMGW.MeterValue]:
        """Fetch data from API endpoint."""

        # The Conexa SMGW is not able to handle multiple concurrent requests, so we need to lock the query.
        # An additional sleep is added to avoid flooding the SMGW
        # because every instance queries the SMGW at the same time (every 15 minutes)
        async with self._query_lock:
            try:
                return await self._api.getLatestValues()
            except ConexaSmgwErr as e:
                raise UpdateFailed(f"Unexpected reply from gateway: {e}") from e
            finally:
                await async_sleep(0.5)

    async def _scheduled_update(self, now: datetime) -> None:
        """Triggered exactly at the time pattern specified in async_init."""
        _LOGGER.debug("Starting scheduled poll at %s", now)
        await self.async_refresh()

    @override
    async def async_shutdown(self) -> None:
        """Cancel any updates before shutting down."""
        if self._scheduled_updates:
            self._scheduled_updates()
            self._scheduled_updates = None

        await super().async_shutdown()
