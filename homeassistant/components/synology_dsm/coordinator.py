"""synology_dsm coordinators."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, TypeVar

from synology_dsm.api.surveillance_station.camera import SynoCamera
from synology_dsm.exceptions import SynologyDSMAPIErrorException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .common import SynoApi
from .const import (
    DEFAULT_SCAN_INTERVAL,
    SIGNAL_CAMERA_SOURCE_CHANGED,
    SYNOLOGY_CONNECTION_EXCEPTIONS,
)

_LOGGER = logging.getLogger(__name__)
_DataT = TypeVar("_DataT")


class SynologyDSMUpdateCoordinator(DataUpdateCoordinator[_DataT]):
    """DataUpdateCoordinator base class for synology_dsm."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: SynoApi,
        update_interval: timedelta,
    ) -> None:
        """Initialize synology_dsm DataUpdateCoordinator."""
        self.api = api
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=f"{entry.title} {self.__class__.__name__}",
            update_interval=update_interval,
        )


class SynologyDSMSwitchUpdateCoordinator(
    SynologyDSMUpdateCoordinator[dict[str, dict[str, Any]]]
):
    """DataUpdateCoordinator to gather data for a synology_dsm switch devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: SynoApi,
    ) -> None:
        """Initialize DataUpdateCoordinator for switch devices."""
        super().__init__(hass, entry, api, timedelta(seconds=30))
        self.version: str | None = None

    async def async_setup(self) -> None:
        """Set up the coordinator initial data."""
        info = await self.api.dsm.surveillance_station.get_info()
        self.version = info["data"]["CMSMinVersion"]

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch all data from api."""
        surveillance_station = self.api.surveillance_station
        return {
            "switches": {"home_mode": await surveillance_station.get_home_mode_status()}
        }


class SynologyDSMCentralUpdateCoordinator(SynologyDSMUpdateCoordinator[None]):
    """DataUpdateCoordinator to gather data for a synology_dsm central device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: SynoApi,
    ) -> None:
        """Initialize DataUpdateCoordinator for central device."""
        super().__init__(
            hass,
            entry,
            api,
            timedelta(
                minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

    async def _async_update_data(self) -> None:
        """Fetch all data from api."""
        try:
            await self.api.async_update()
        except SYNOLOGY_CONNECTION_EXCEPTIONS as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return None


class SynologyDSMCameraUpdateCoordinator(
    SynologyDSMUpdateCoordinator[dict[str, dict[str, SynoCamera]]]
):
    """DataUpdateCoordinator to gather data for a synology_dsm cameras."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: SynoApi,
    ) -> None:
        """Initialize DataUpdateCoordinator for cameras."""
        super().__init__(hass, entry, api, timedelta(seconds=30))

    async def _async_update_data(self) -> dict[str, dict[str, SynoCamera]]:
        """Fetch all camera data from api."""
        surveillance_station = self.api.surveillance_station
        current_data: dict[str, SynoCamera] = {
            camera.id: camera for camera in surveillance_station.get_all_cameras()
        }

        try:
            await surveillance_station.update()
        except SynologyDSMAPIErrorException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        new_data: dict[str, SynoCamera] = {
            camera.id: camera for camera in surveillance_station.get_all_cameras()
        }

        for cam_id, cam_data_new in new_data.items():
            if (
                (cam_data_current := current_data.get(cam_id)) is not None
                and cam_data_current.live_view.rtsp != cam_data_new.live_view.rtsp
            ):
                async_dispatcher_send(
                    self.hass,
                    f"{SIGNAL_CAMERA_SOURCE_CHANGED}_{self.entry.entry_id}_{cam_id}",
                    cam_data_new.live_view.rtsp,
                )

        return {"cameras": new_data}
