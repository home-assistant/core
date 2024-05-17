"""synology_dsm coordinators."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any, Concatenate, TypeVar

from synology_dsm.api.surveillance_station.camera import SynoCamera
from synology_dsm.exceptions import (
    SynologyDSMAPIErrorException,
    SynologyDSMNotLoggedInException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .common import SynoApi, raise_config_entry_auth_error
from .const import (
    DEFAULT_SCAN_INTERVAL,
    SIGNAL_CAMERA_SOURCE_CHANGED,
    SYNOLOGY_AUTH_FAILED_EXCEPTIONS,
    SYNOLOGY_CONNECTION_EXCEPTIONS,
)

_LOGGER = logging.getLogger(__name__)
_DataT = TypeVar("_DataT")


def async_re_login_on_expired[_T: SynologyDSMUpdateCoordinator[Any], **_P, _R](
    func: Callable[Concatenate[_T, _P], Awaitable[_R]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]]:
    """Define a wrapper to re-login when expired."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        for attempts in range(2):
            try:
                return await func(self, *args, **kwargs)
            except SynologyDSMNotLoggedInException:
                # If login is expired, try to login again
                _LOGGER.debug("login is expired, try to login again")
                try:
                    await self.api.async_login()
                except SYNOLOGY_AUTH_FAILED_EXCEPTIONS as err:
                    raise_config_entry_auth_error(err)
                if attempts == 0:
                    continue
            except SYNOLOGY_CONNECTION_EXCEPTIONS as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

        raise UpdateFailed("Unknown error when communicating with API")

    return _async_wrap


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
        assert info is not None
        self.version = info["data"]["CMSMinVersion"]

    @async_re_login_on_expired
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch all data from api."""
        surveillance_station = self.api.surveillance_station
        assert surveillance_station is not None
        return {
            "switches": {
                "home_mode": bool(await surveillance_station.get_home_mode_status())
            }
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

    @async_re_login_on_expired
    async def _async_update_data(self) -> None:
        """Fetch all data from api."""
        await self.api.async_update()


class SynologyDSMCameraUpdateCoordinator(
    SynologyDSMUpdateCoordinator[dict[str, dict[int, SynoCamera]]]
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

    @async_re_login_on_expired
    async def _async_update_data(self) -> dict[str, dict[int, SynoCamera]]:
        """Fetch all camera data from api."""
        surveillance_station = self.api.surveillance_station
        assert surveillance_station is not None
        current_data: dict[int, SynoCamera] = {
            camera.id: camera for camera in surveillance_station.get_all_cameras()
        }

        try:
            await surveillance_station.update()
        except SynologyDSMAPIErrorException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        new_data: dict[int, SynoCamera] = {
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
