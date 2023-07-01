"""Support for Vodafone Station."""
import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta

import aiohttp
from aiovodafone.api import VodafoneStationApi, VodafoneStationDevice

from homeassistant.components.device_tracker import DEFAULT_CONSIDER_HOME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import _LOGGER, DOMAIN


class VodafoneStationDeviceInfo:
    """Representation of a device connected to the Vodafone Station."""

    def __init__(self, mac: str, name: str | None = None) -> None:
        """Initialize device info."""
        self._connected = False
        self._connection_type: str | None = None
        self._ip_address: str | None = None
        self._last_activity: datetime | None = None
        self._mac = mac
        self._name = name
        self._wifi: str | None = None

    def update(
        self,
        dev_info: VodafoneStationDevice,
        consider_home: float = DEFAULT_CONSIDER_HOME.total_seconds(),
    ) -> None:
        """Update device info."""
        utc_point_in_time = dt_util.utcnow()

        if self._last_activity:
            consider_home_evaluated = (
                utc_point_in_time - self._last_activity
            ).total_seconds() < consider_home
        else:
            consider_home_evaluated = dev_info.connected

        if not self._name:
            self._name = dev_info.name or self._mac.replace(":", "_")

        self._connected = dev_info.connected or consider_home_evaluated

        if dev_info.connected:
            self._last_activity = utc_point_in_time

        self._connection_type = dev_info.connection_type
        self._ip_address = dev_info.ip_address
        self._wifi = dev_info.wifi

    @property
    def connection_type(self) -> str:
        """Return connected status."""
        return self._connection_type or ""

    @property
    def is_connected(self) -> bool:
        """Return connected status."""
        return self._connected

    @property
    def mac_address(self) -> str:
        """Get MAC address."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Get Name."""
        return self._name

    @property
    def ip_address(self) -> str | None:
        """Get IP address."""
        return self._ip_address

    @property
    def last_activity(self) -> datetime | None:
        """Return device last activity."""
        return self._last_activity

    @property
    def wifi(self) -> str | None:
        """Return device WIFi connection."""
        return self._wifi


class VodafoneStationRouter(DataUpdateCoordinator):
    """Queries router running Vodafone Station firmware."""

    def __init__(
        self, host: str, ssl: bool, username: str, password: str, hass: HomeAssistant
    ) -> None:
        """Initialize the scanner."""

        self._host = host
        self._devices: dict[str, VodafoneStationDeviceInfo] = {}
        self._data: dict[str, str] = {}
        self._on_close: list[Callable] = []

        self.api = VodafoneStationApi(host, ssl, username, password)

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=30),
        )

    @callback
    def async_listener(self) -> None:
        """Fetch data from the router."""

        asyncio.run_coroutine_threadsafe(self._async_update_data(), self.hass.loop)

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    async def _async_update_data(self) -> bool:
        """Update router data."""
        _LOGGER.debug("Polling Vodafone Station host: %s", self._host)
        try:
            logged = await self.api.login()
        except (asyncio.exceptions.TimeoutError, aiohttp.ClientConnectorError) as err:
            _LOGGER.warning("Connection error for %s", self._host)
            raise UpdateFailed(f"Error fetching data: {repr(err)}") from err

        if not logged:
            raise ConfigEntryAuthFailed

        devices = await self.api.get_all_devices()
        dev_info: VodafoneStationDevice
        for _, dev_info in devices.items():
            dev = VodafoneStationDeviceInfo(dev_info.mac, dev_info.name)
            dev.update(dev_info)
            self._devices[dev_info.mac] = dev
        self._data = await self.api.get_user_data()

        await self.api.logout()

        return True

    @property
    def devices(self) -> dict[str, VodafoneStationDeviceInfo]:
        """Return a list of devices."""
        return self._devices

    @property
    def signal_device_new(self) -> str:
        """Event specific per Vodafone Station entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._host}"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Vodafone Station entry to signal updates in devices."""
        return f"{DOMAIN}-device-update-{self._host}"
