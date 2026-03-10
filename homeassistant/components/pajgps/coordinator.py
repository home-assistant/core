"""DataUpdateCoordinator for the PAJ GPS integration."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
import logging

import aiohttp
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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class PajGpsData:
    """Snapshot of all PAJ GPS data for one coordinator tick."""

    devices: list[Device] = dataclasses.field(default_factory=list)
    positions: dict[int, TrackPoint] = dataclasses.field(default_factory=dict)


class PajGpsCoordinator(DataUpdateCoordinator[PajGpsData]):
    """Coordinator for the PAJ GPS integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        websession: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the coordinator from config-entry data."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            config_entry=config_entry,
        )

        self.guid: str = config_entry.data["guid"]
        self.api = PajGpsApi(
            email=config_entry.data[CONF_EMAIL],
            password=config_entry.data[CONF_PASSWORD],
            websession=websession,
        )
        self._owns_websession = websession is None

        # Snapshot starts empty; entities must handle None gracefully until first refresh
        self.data = PajGpsData()

    async def _async_setup(self) -> None:
        """Perform initial and first data refresh."""
        try:
            await self.api.login()
        except (AuthenticationError, TokenRefreshError) as exc:
            raise UpdateFailed(f"PAJ GPS authentication failed: {exc}") from exc
        except Exception as exc:
            raise UpdateFailed(f"PAJ GPS connection error: {exc}") from exc

    async def _async_update_data(self) -> PajGpsData:
        """Fetch device list and positions every UPDATE_INTERVAL seconds."""
        try:
            devices = await self.api.get_devices()
        except PajGpsApiError as exc:
            raise UpdateFailed(f"Failed to fetch device list: {exc}") from exc

        device_ids = [d.id for d in devices if d.id is not None]
        positions: dict[int, TrackPoint] = {}
        if device_ids:
            try:
                track_points = await self.api.get_all_last_positions(device_ids)
                positions = {
                    tp.iddevice: tp for tp in track_points if tp.iddevice is not None
                }
            except PajGpsApiError as exc:
                _LOGGER.warning("Failed to fetch positions: %s", exc)

        return PajGpsData(devices=devices, positions=positions)

    def get_device_info(self, device_id: int) -> DeviceInfo | None:
        """Return the HA DeviceInfo dict for the given device_id."""
        for device in self.data.devices:
            if device.id == device_id:
                model = "Unknown"
                device_models = getattr(device, "device_models", None)
                if device_models and isinstance(device_models[0], dict):
                    model = device_models[0].get("model") or "Unknown"

                return DeviceInfo(
                    identifiers={(DOMAIN, f"{self.guid}_{device_id}")},
                    name=device.name or f"PAJ GPS {device_id}",
                    manufacturer="PAJ GPS",
                    model=model,
                )
        return None

    async def async_shutdown(self) -> None:
        """Clean up all resources owned by this coordinator."""
        if self._owns_websession:
            await self.api.close()
