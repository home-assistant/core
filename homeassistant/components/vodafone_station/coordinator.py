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

    def __init__(
        self,
        dev_info: VodafoneStationDevice,
        coordinator: DataUpdateCoordinator,
        consider_home: float = DEFAULT_CONSIDER_HOME.total_seconds(),
    ) -> None:
        """Initialize device info."""
        self._dev_info = dev_info
        self._consider_home = consider_home
        self._coordinator = coordinator
        self._utc_point_in_time = dt_util.utcnow()

        self.connection_type: str = self._dev_info.connection_type
        self.hostname = self._dev_info.name or self._dev_info.mac.replace(":", "_")
        self.ip_address: str = self._dev_info.ip_address
        self.mac_address = self._dev_info.mac
        self.wifi: str = self._dev_info.wifi

        self.last_activity: datetime | None = self._last_activity_status_update()
        self.is_connected = self._connected_status_update()

    def _last_activity_status_update(self) -> datetime | None:
        """Update last_activity status."""

        if self._dev_info.connected:
            return self._utc_point_in_time

        if self._coordinator.data:
            return self._coordinator.data.devices[self._dev_info.mac].last_activity

        return None

    def _connected_status_update(self) -> bool:
        """Update connected status."""

        if self._dev_info.connected:
            return True

        consider_home_evaluated = False
        if self.last_activity:
            consider_home_evaluated = (
                self._utc_point_in_time - self.last_activity
            ).total_seconds() < self._consider_home

        return consider_home_evaluated


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
            data.devices[dev_info.mac] = VodafoneStationDeviceInfo(dev_info, self)
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
