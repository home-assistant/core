"""DataUpdateCoordinator for the PAJ GPS integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from pajgps_api import PajGpsApi
from pajgps_api.models.device import Device
from pajgps_api.models.sensordata import SensorData
from pajgps_api.models.trackpoint import TrackPoint
from pajgps_api.pajgps_api_error import (
    AuthenticationError,
    PajGpsApiError,
    TokenRefreshError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type PajGpsConfigEntry = ConfigEntry[PajGpsCoordinator]


@dataclass
class PajGpsData:
    """Snapshot of all PAJ GPS data for one coordinator tick."""

    devices: dict[int, Device]
    positions: dict[int, TrackPoint]
    sensor_data: dict[int, SensorData]


class PajGpsCoordinator(DataUpdateCoordinator[PajGpsData]):
    """Coordinator for the PAJ GPS integration."""

    config_entry: PajGpsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PajGpsConfigEntry,
    ) -> None:
        """Initialize the coordinator from config-entry data."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            config_entry=config_entry,
        )

        self._email: str = config_entry.data[CONF_EMAIL]
        self._user_id: int | None = None
        self._voltage_data_failures: set[int] = set()
        self.api = PajGpsApi(
            email=self._email,
            password=config_entry.data[CONF_PASSWORD],
            websession=async_get_clientsession(hass),
        )

    @property
    def email(self) -> str:
        """Return the account email address for this coordinator."""
        return self._email

    @property
    def user_id(self) -> int | None:
        """Return the user ID obtained from the login response."""
        return self._user_id

    @override
    async def _async_setup(self) -> None:
        """Perform initial and first data refresh."""
        try:
            auth = await self.api.login()
            self._user_id = auth.userID
        except (AuthenticationError, TokenRefreshError) as exc:
            raise ConfigEntryAuthFailed from exc
        except Exception as exc:
            raise ConfigEntryNotReady from exc

    @override
    async def _async_update_data(self) -> PajGpsData:
        """Fetch device list and positions."""
        devices: dict[int, Device] = {}
        try:
            device_list = await self.api.get_devices()
            devices = {
                device.id: device for device in device_list if device.id is not None
            }
        except PajGpsApiError as exc:
            raise UpdateFailed(f"Failed to fetch device list: {exc}") from exc

        device_ids = list(devices.keys())
        positions: dict[int, TrackPoint] = {}
        if device_ids:
            try:
                track_points = await self.api.get_all_last_positions(device_ids)
            except PajGpsApiError as exc:
                raise UpdateFailed(f"Failed to fetch positions: {exc}") from exc
            positions = {
                tp.iddevice: tp for tp in track_points if tp.iddevice is not None
            }

        sensor_data: dict[int, SensorData] = {}
        voltage_device_ids = [
            device_id
            for device_id, device in devices.items()
            if device.has_voltage_sensor
        ]

        if voltage_device_ids:
            results = await asyncio.gather(
                *(
                    self.api.get_last_sensor_data(device_id)
                    for device_id in voltage_device_ids
                ),
                return_exceptions=True,
            )

            for device_id, result in zip(voltage_device_ids, results, strict=False):
                if isinstance(result, PajGpsApiError):
                    if device_id not in self._voltage_data_failures:
                        _LOGGER.info(
                            "Failed to fetch voltage sensor data for device %s: %s",
                            device_id,
                            result,
                        )
                        self._voltage_data_failures.add(device_id)
                    continue
                if isinstance(result, BaseException):
                    raise result
                if device_id in self._voltage_data_failures:
                    _LOGGER.info(
                        "Voltage sensor data recovered for device %s", device_id
                    )
                    self._voltage_data_failures.remove(device_id)
                sensor_data[device_id] = result

        return PajGpsData(devices=devices, positions=positions, sensor_data=sensor_data)
