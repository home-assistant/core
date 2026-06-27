"""Coordinator for the Theben Conexa Smartmeter gateway integration."""

from datetime import datetime
import logging
from typing import override

import aiohttp
from theben_conexa_smgw import ConexaSMGW, checkNetworkConnection

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

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

    async def async_init(self) -> None:
        """Asynchronous Initialization and registering the update schedule."""

        try:
            # This function tries to establish a TCP connection and raises an exception on error
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

        _LOGGER.debug("Fetching data from API")
        vals = await self._api.getLatestValues()

        if _LOGGER.isEnabledFor(logging.DEBUG) and vals:
            now_utc = dt_util.utcnow()
            meter_timestamp: str = next(iter(vals.values())).utcTimestamp
            meter_datetime = dt_util.parse_datetime(meter_timestamp)
            if meter_datetime is None:
                _LOGGER.warning("Could not parse meter timestamp: %s", meter_timestamp)
                return vals
            age = (now_utc - meter_datetime).total_seconds()
            _LOGGER.debug(
                "Data fetched at %s: %s (data age %s sec)", now_utc, vals, age
            )

        return vals

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
