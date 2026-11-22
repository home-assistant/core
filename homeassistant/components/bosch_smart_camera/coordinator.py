"""Coordinator for the Bosch Smart Camera integration."""

import asyncio
from collections import defaultdict
from dataclasses import replace
from datetime import timedelta
import logging
import time
from typing import override

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
)
from bosch_shc_camera_client.client import BoschCameraClient
from bosch_shc_camera_client.states import CameraAccountStates

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# The camera list only changes when the user adds or removes a camera.
SCAN_INTERVAL = timedelta(minutes=5)

# Dashboards request the image often, but the latest event rarely changes.
SNAPSHOT_TTL = 60

type BoschCameraConfigEntry = ConfigEntry[BoschCameraCoordinator]


class BoschCameraCoordinator(DataUpdateCoordinator[dict[str, Camera]]):
    """Fetch the cameras of the account."""

    config_entry: BoschCameraConfigEntry
    _oauth_session: OAuth2Session
    _client: BoschCameraClient

    def __init__(
        self, hass: HomeAssistant, config_entry: BoschCameraConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.account_states: dict[str, CameraAccountStates] = {}
        self._write_seq = 0
        self._written_at: dict[str, int] = {}
        self.motion_states: dict[str, bool] = {}
        self._motion_writes: defaultdict[str, int] = defaultdict(int)
        self._motion_unreachable: set[str] = set()
        self._snapshots: dict[str, tuple[float, bytes | None]] = {}
        self._snapshot_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @override
    async def _async_setup(self) -> None:
        """Resolve the OAuth2 implementation and the shared HTTP session."""
        implementation = await async_get_config_entry_implementation(
            self.hass, self.config_entry
        )
        self._oauth_session = OAuth2Session(
            self.hass, self.config_entry, implementation
        )
        self._client = BoschCameraClient(
            async_get_clientsession(self.hass), self._async_get_token
        )

    async def _async_get_token(self) -> str:
        """Return a fresh access token."""
        await self._oauth_session.async_ensure_token_valid()
        return str(self._oauth_session.token[CONF_ACCESS_TOKEN])

    @override
    async def _async_update_data(self) -> dict[str, Camera]:
        """Fetch the camera list."""
        started = self._write_seq
        try:
            cameras = await self._client.list_cameras()
            states = await self._client.get_camera_account_states()
        except BoschCameraAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except (BoschCameraConnectionError, BoschCameraInvalidResponseError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        # A response that predates a write must not undo it.
        for camera_id, written in self._written_at.items():
            if written > started and camera_id in self.account_states:
                states[camera_id] = self.account_states[camera_id]
        self.account_states = states
        self._written_at = {
            camera_id: written
            for camera_id, written in self._written_at.items()
            if written > started
        }
        data = {camera.id: camera for camera in cameras}
        await self._async_update_motion_states(cameras)
        for camera_id in self._snapshots.keys() - data.keys():
            del self._snapshots[camera_id]
            self._snapshot_locks.pop(camera_id, None)
        self._sync_devices(data)
        return data

    async def _async_update_motion_states(self, cameras: list[Camera]) -> None:
        """Poll the motion detection of each camera, isolating failures."""
        polled: dict[str, tuple[int, bool | None]] = {}
        for camera in cameras:
            writes = self._motion_writes[camera.id]
            try:
                settings = await self._client.get_motion_settings(camera.id)
            except BoschCameraAuthError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="auth_failed"
                ) from err
            except BoschCameraConnectionError, BoschCameraInvalidResponseError:
                if camera.id not in self._motion_unreachable:
                    self._motion_unreachable.add(camera.id)
                    _LOGGER.info(
                        "The motion detection of %s is unreachable", camera.title
                    )
                _LOGGER.debug(
                    "Unable to read the motion detection of a camera", exc_info=True
                )
                enabled = None
            else:
                if camera.id in self._motion_unreachable:
                    self._motion_unreachable.discard(camera.id)
                    _LOGGER.info(
                        "The motion detection of %s is reachable again", camera.title
                    )
                enabled = settings.enabled
            polled[camera.id] = (writes, enabled)
        # A write that finished while polling outdates the polled state, also
        # for cameras polled before the write.
        states: dict[str, bool] = {}
        for camera_id, (writes, enabled) in polled.items():
            if writes != self._motion_writes[camera_id]:
                enabled = self.motion_states.get(camera_id)
            if enabled is not None:
                states[camera_id] = enabled
        self.motion_states = states

    async def async_get_snapshot(self, camera_id: str) -> bytes | None:
        """Return the image of the camera's latest event, cached briefly."""
        async with self._snapshot_locks[camera_id]:
            cached = self._snapshots.get(camera_id)
            if cached and time.monotonic() - cached[0] < SNAPSHOT_TTL:
                return cached[1]
            try:
                image = await self._client.get_latest_event_image(camera_id)
            except (
                BoschCameraAuthError,
                BoschCameraConnectionError,
                BoschCameraInvalidResponseError,
            ) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="snapshot_failed"
                ) from err
            self._snapshots[camera_id] = (time.monotonic(), image)
            return image

    async def async_set_privacy_mode(self, camera_id: str, enabled: bool) -> None:
        """Switch the privacy mode of a camera and update the cached state."""
        result = await self._client.set_privacy_mode(camera_id, enabled)
        if result.status in (401, 403):
            self.config_entry.async_start_reauth_if_available(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            )
        if not result.ok:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="privacy_mode_failed"
            )
        # The camera may have been removed while the write was running.
        if (state := self.account_states.get(camera_id)) is None:
            return
        # The camera list is only polled every few minutes.
        self._write_seq += 1
        self._written_at[camera_id] = self._write_seq
        self.account_states[camera_id] = replace(state, privacy_mode=enabled)
        self.async_update_listeners()

    async def async_set_motion_detection(self, camera_id: str, enabled: bool) -> None:
        """Switch the motion detection of a camera and update the cached state."""
        try:
            await self._client.set_motion_enabled(camera_id, enabled)
        except BoschCameraAuthError as err:
            self.config_entry.async_start_reauth_if_available(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except (BoschCameraConnectionError, BoschCameraInvalidResponseError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="motion_detection_failed"
            ) from err
        # The camera may have been removed while the write was running.
        if camera_id not in self.data:
            return
        # The camera may revert the write within a second, so the next poll wins.
        self._motion_writes[camera_id] += 1
        self.motion_states[camera_id] = enabled
        self.async_update_listeners()

    def _sync_devices(self, cameras: dict[str, Camera]) -> None:
        """Remove devices of cameras no longer in the account, refresh the rest."""
        device_registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            camera = next(
                (
                    cameras[camera_id]
                    for domain, camera_id in device.identifiers
                    if domain == DOMAIN and camera_id in cameras
                ),
                None,
            )
            if camera is None:
                device_registry.async_remove_device(device.id)
            elif (
                device.name != camera.title
                or device.sw_version != camera.firmware_version
            ):
                device_registry.async_update_device(
                    device.id, name=camera.title, sw_version=camera.firmware_version
                )
