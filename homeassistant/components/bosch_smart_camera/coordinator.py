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
    CameraModel,
)
from bosch_shc_camera_client.client import BoschCameraClient
from bosch_shc_camera_client.cloud import cloud_set_camera_light
from bosch_shc_camera_client.settings import AudioSettings
from bosch_shc_camera_client.states import (
    CameraAccountStates,
    LightState,
    get_light_state,
)

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
        self.light_states: dict[str, LightState] = {}
        self._light_writes: defaultdict[str, int] = defaultdict(int)
        self._light_unreachable: set[str] = set()
        self._write_seq = 0
        self._written_at: dict[str, int] = {}
        self.audio_settings: dict[str, AudioSettings] = {}
        self._audio_writes: defaultdict[str, int] = defaultdict(int)
        self._audio_unreachable: set[str] = set()
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
        await self._async_update_audio_settings(cameras)
        await self._async_update_light_states(cameras)
        for camera_id in self._snapshots.keys() - data.keys():
            del self._snapshots[camera_id]
            self._snapshot_locks.pop(camera_id, None)
        self._sync_devices(data)
        return data

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

    async def _async_update_light_states(self, cameras: list[Camera]) -> None:
        """Poll the light of each Gen1 outdoor camera, isolating failures."""
        # Forget removed cameras so a camera that comes back is logged again.
        listed = {camera.id for camera in cameras}
        self._light_unreachable &= listed
        for camera_id in self._light_writes.keys() - listed:
            del self._light_writes[camera_id]
        polled: dict[str, tuple[int, LightState | None]] = {}
        for camera in cameras:
            if camera.model is not CameraModel.EYES_OUTDOOR:
                continue
            writes = self._light_writes[camera.id]
            try:
                state = await get_light_state(
                    async_get_clientsession(self.hass),
                    await self._async_get_token(),
                    camera.id,
                )
            except BoschCameraAuthError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="auth_failed"
                ) from err
            except BoschCameraConnectionError, BoschCameraInvalidResponseError:
                if camera.id not in self._light_unreachable:
                    self._light_unreachable.add(camera.id)
                    _LOGGER.info("The light of %s is unreachable", camera.title)
                _LOGGER.debug("Unable to read the light of a camera", exc_info=True)
                state = None
            else:
                if camera.id in self._light_unreachable:
                    self._light_unreachable.discard(camera.id)
                    _LOGGER.info("The light of %s is reachable again", camera.title)
            polled[camera.id] = (writes, state)
        # A write that finished while polling makes the polled state outdated,
        # also for cameras polled before the write.
        states: dict[str, LightState] = {}
        for camera_id, (writes, state) in polled.items():
            if writes != self._light_writes[camera_id]:
                state = self.light_states.get(camera_id)
            if state is not None:
                states[camera_id] = state
        self.light_states = states

    async def async_set_light(self, camera_id: str, on: bool) -> None:
        """Switch the light of a camera and remember the new state."""
        known = self.light_states.get(camera_id)
        intensity = known.front_light_intensity if known else None
        try:
            result = await cloud_set_camera_light(
                async_get_clientsession(self.hass),
                await self._async_get_token(),
                camera_id,
                on,
                gen2=False,
                last_front_intensity=intensity or 1.0,
            )
        except BoschCameraAuthError as err:
            self.config_entry.async_start_reauth_if_available(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except BoschCameraConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="light_failed"
            ) from err
        if result.status in (401, 403):
            self.config_entry.async_start_reauth_if_available(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            )
        if not result.ok:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="light_failed"
            )
        self._light_writes[camera_id] += 1
        self.light_states[camera_id] = LightState(
            front_light_on=on,
            wallwasher_on=on,
            front_light_intensity=intensity,
        )
        self.async_update_listeners()

    async def _async_update_audio_settings(self, cameras: list[Camera]) -> None:
        """Poll the audio settings of each camera, isolating failures."""
        # Forget removed cameras so a camera that comes back is logged again.
        listed = {camera.id for camera in cameras}
        self._audio_unreachable &= listed
        for camera_id in self._audio_writes.keys() - listed:
            del self._audio_writes[camera_id]
        polled: dict[str, tuple[int, AudioSettings | None]] = {}
        for camera in cameras:
            writes = self._audio_writes[camera.id]
            try:
                settings = await self._client.get_audio_settings(camera.id)
            except BoschCameraAuthError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="auth_failed"
                ) from err
            except BoschCameraConnectionError, BoschCameraInvalidResponseError:
                if camera.id not in self._audio_unreachable:
                    self._audio_unreachable.add(camera.id)
                    _LOGGER.info(
                        "The audio settings of %s are unreachable", camera.title
                    )
                _LOGGER.debug("Unable to read the audio settings", exc_info=True)
                settings = None
            else:
                if camera.id in self._audio_unreachable:
                    self._audio_unreachable.discard(camera.id)
                    _LOGGER.info(
                        "The audio settings of %s are reachable again", camera.title
                    )
            polled[camera.id] = (writes, settings)
        # A write that finished while polling makes the polled state outdated,
        # also for cameras polled before the write.
        current: dict[str, AudioSettings] = {}
        for camera_id, (writes, settings) in polled.items():
            if writes != self._audio_writes[camera_id]:
                settings = self.audio_settings.get(camera_id)
            if settings is not None:
                current[camera_id] = settings
        self.audio_settings = current

    async def async_set_speaker_level(self, camera_id: str, level: int) -> None:
        """Set the speaker level of a camera and update the cached settings."""
        try:
            await self._client.set_audio_settings(camera_id, speaker_level=level)
        except BoschCameraAuthError as err:
            self.config_entry.async_start_reauth_if_available(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except (BoschCameraConnectionError, BoschCameraInvalidResponseError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="speaker_level_failed"
            ) from err
        # The camera may have been removed while the write was running.
        if camera_id not in self.data:
            return
        self._audio_writes[camera_id] += 1
        known = self.audio_settings.get(camera_id) or AudioSettings(
            None, None, None, {}
        )
        self.audio_settings[camera_id] = replace(known, speaker_level=level)
        self.async_update_listeners()

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
