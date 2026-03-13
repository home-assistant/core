"""DataUpdateCoordinator for the PAJ GPS integration."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
import logging

from pajgps_api import PajGpsApi
from pajgps_api.models.device import Device
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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type PajGpsConfigEntry = ConfigEntry[PajGpsCoordinator]


@dataclasses.dataclass(frozen=True)
class PajGpsData:
    """Snapshot of all PAJ GPS data for one coordinator tick."""

    devices: dict[int, Device]
    positions: dict[int, TrackPoint]


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
        self.api = PajGpsApi(
            email=config_entry.data[CONF_EMAIL],
            password=config_entry.data[CONF_PASSWORD],
            websession=async_get_clientsession(hass),
        )

    @property
    def email(self) -> str:
        """Return the account email address for this coordinator."""
        return self._email

    async def _async_setup(self) -> None:
        """Perform initial and first data refresh."""
        try:
            await self.api.login()
        except (AuthenticationError, TokenRefreshError) as exc:
            raise ConfigEntryAuthFailed from exc
        except Exception as exc:
            raise ConfigEntryNotReady from exc

    async def _async_update_data(self) -> PajGpsData:
        """Fetch device list and positions every UPDATE_INTERVAL seconds."""
        devices: dict[int, Device] = {}
        try:
            devices = await self.api.get_devices()
        except PajGpsApiError as exc:
            raise UpdateFailed(f"Failed to fetch device list: {exc}") from exc

        device_ids = list(devices.keys())
        positions: dict[int, TrackPoint] = {}
        if device_ids:
            try:
                track_points = await self.api.get_all_last_positions(device_ids)
                positions = {
                    tp.iddevice: tp for tp in track_points if tp.iddevice is not None
                }
            except PajGpsApiError as exc:
                raise UpdateFailed(f"Failed to fetch positions: {exc}") from exc

        return PajGpsData(devices=devices, positions=positions)

    def get_device_info(self, device_id: int) -> DeviceInfo | None:
        """Return the HA DeviceInfo dict for the given device_id."""
        device = self.data.devices.get(device_id)
        if device and device.id == device_id:
            model = None
            device_models = getattr(device, "device_models", None)
            if device_models and isinstance(device_models[0], dict):
                model = device_models[0].get("model") or None

            return DeviceInfo(
                identifiers={(DOMAIN, f"{self.config_entry.entry_id}_{device_id}")},
                name=device.name or f"PAJ GPS {device_id}",
                manufacturer="PAJ GPS",
                model=model,
            )
        return None
