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

CONSIDER_HOME_SECONDS = DEFAULT_CONSIDER_HOME.total_seconds()


@dataclass(slots=True)
class VodafoneStationDeviceInfo:
    """Representation of a device connected to the Vodafone Station."""

    device: VodafoneStationDevice
    update_time: datetime | None


@dataclass(slots=True)
class UpdateCoordinatorDataType:
    """Update coordinator data type."""

    devices: dict[str, VodafoneStationDeviceInfo]
    sensors: dict[str, Any]


class VodafoneStationRouter(DataUpdateCoordinator[UpdateCoordinatorDataType]):
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

    def _device_evaluate_status(
        self, device: VodafoneStationDevice
    ) -> tuple[datetime | None, bool]:
        """Evaluate status consider home and last activity."""

        utc_point_in_time = dt_util.utcnow()

        if device.connected:
            return utc_point_in_time, True

        if (
            self.data
            and self.data.devices
            and (stored_device := self.data.devices.get(device.mac))
        ):
            consider_home_evaluated = False
            update_time = stored_device.update_time
            if update_time:
                consider_home_evaluated = (
                    utc_point_in_time - update_time
                ).total_seconds() < CONSIDER_HOME_SECONDS

            return update_time, consider_home_evaluated

        return None, False

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

        data_devices = {}
        data_sensors = {}
        list_devices = await self.api.get_all_devices()
        dev_info: VodafoneStationDevice
        for dev_info in list_devices.values():
            update_time, dev_info.connected = self._device_evaluate_status(dev_info)
            data_devices[dev_info.mac] = VodafoneStationDeviceInfo(
                dev_info, update_time
            )
        data_sensors = await self.api.get_user_data()

        await self.api.logout()

        return UpdateCoordinatorDataType(data_devices, data_sensors)

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
