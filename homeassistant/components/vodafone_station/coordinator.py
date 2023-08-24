"""Support for Vodafone Station."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from aiovodafone import VodafoneStationApi, VodafoneStationDevice, exceptions

from homeassistant.components.device_tracker import DEFAULT_CONSIDER_HOME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import _LOGGER, DOMAIN


class VodafoneStationDeviceInfo:
    """Representation of a device connected to the Vodafone Station."""

    def __init__(self, dev_info: VodafoneStationDevice) -> None:
        """Initialize device info."""
        self._connected = False
        self._connection_type: str | None = None
        self._ip_address: str | None = None
        self._last_activity: datetime | None = None
        self._mac = dev_info.mac
        self._name = dev_info.name
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


@dataclass
class UpdateCoordinatorDataType:
    """Update coordinator data type."""

    devices: dict[str, VodafoneStationDeviceInfo]
    sensors: dict[str, Any]


class VodafoneStationRouter(DataUpdateCoordinator):
    """Queries router running Vodafone Station firmware."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        config_entry_unique_id: str | None,
    ) -> None:
        """Initialize the scanner."""

        self._host = host
        self.api = VodafoneStationApi(host, username, password)

        # Last resort as no MAC or S/N can be retrieved via API
        self._id = config_entry_unique_id

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> UpdateCoordinatorDataType:
        """Update router data."""
        _LOGGER.debug("Polling Vodafone Station host: %s", self._host)
        try:
            logged = await self.api.login()
        except exceptions.CannotConnect as err:
            _LOGGER.warning("Connection error for %s", self._host)
            raise UpdateFailed(f"Error fetching data: {repr(err)}") from err
        except exceptions.CannotAuthenticate as err:
            raise ConfigEntryAuthFailed from err

        if not logged:
            raise ConfigEntryAuthFailed

        data = UpdateCoordinatorDataType({}, {})
        list_devices = await self.api.get_all_devices()
        dev_info: VodafoneStationDevice
        for dev_info in list_devices.values():
            dev = VodafoneStationDeviceInfo(dev_info)
            dev.update(dev_info)
            data.devices[dev_info.mac] = dev
        data.sensors = await self.api.get_user_data()

        await self.api.logout()

        return data

    async def async_send_signal_device_update(self, new_device: bool) -> None:
        """Signal device data updated."""
        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    @property
    def signal_device_new(self) -> str:
        """Event specific per Vodafone Station entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._id}"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Vodafone Station entry to signal updates in devices."""
        return f"{DOMAIN}-device-update-{self._id}"
