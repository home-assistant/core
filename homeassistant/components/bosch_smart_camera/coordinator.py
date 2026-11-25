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
from bosch_shc_camera_client.states import (
    CameraAccountStates,
    LightState,
    get_light_state,
    get_wifi_info,
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

# The signal strength fluctuates, but a diagnostic value needs no tight polling.
WIFI_SCAN_INTERVAL = timedelta(minutes=10)

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
        self._written_at: dict[tuple[str, str], int] = {}
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
        # A response that predates a write must not undo it, even when it omits
        # the state of a camera that is still listed.
        listed = {camera.id for camera in cameras}
        for (camera_id, field), written in self._written_at.items():
            if (
                written <= started
                or (cached := self.account_states.get(camera_id)) is None
            ):
                continue
            if camera_id in states:
                states[camera_id] = replace(
                    states[camera_id], **{field: getattr(cached, field)}
                )
            elif camera_id in listed:
                states[camera_id] = cached
        self.account_states = states
        self._written_at = {
            key: written
            for key, written in self._written_at.items()
            if written > started
        }
        data = {camera.id: camera for camera in cameras}
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

    def _written_state(self, camera_id: str) -> CameraAccountStates | None:
        """Return the state to apply a write to, None if the camera was removed."""
        if (state := self.account_states.get(camera_id)) is not None:
            return state
        # A poll may omit the state of a camera that is still listed.
        if camera_id in self.data:
            return CameraAccountStates(None, None)
        return None

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
        if (state := self._written_state(camera_id)) is None:
            return
        # The camera list is only polled every few minutes.
        self._write_seq += 1
        self._written_at[camera_id, "privacy_mode"] = self._write_seq
        self.account_states[camera_id] = replace(state, privacy_mode=enabled)
        self.async_update_listeners()

    async def async_set_notifications(self, camera_id: str, enabled: bool) -> None:
        """Switch the push notifications of a camera and update the cached state."""
        result = await self._client.set_notifications(camera_id, enabled)
        if result.status in (401, 403):
            self.config_entry.async_start_reauth_if_available(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            )
        if not result.ok:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="notifications_failed"
            )
        if (state := self._written_state(camera_id)) is None:
            return
        # The camera list is only polled every few minutes.
        self._write_seq += 1
        self._written_at[camera_id, "notifications_status"] = self._write_seq
        self.account_states[camera_id] = replace(
            state,
            notifications_status="FOLLOW_CAMERA_SCHEDULE" if enabled else "ALWAYS_OFF",
        )
        self.async_update_listeners()

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return str(self._oauth_session.token[CONF_ACCESS_TOKEN])

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


class BoschWifiCoordinator(DataUpdateCoordinator[dict[str, int | None]]):
    """Fetch the Wi-Fi signal strength of every camera."""

    config_entry: BoschCameraConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BoschCameraConfigEntry,
        cameras: BoschCameraCoordinator,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_wifi",
            update_interval=WIFI_SCAN_INTERVAL,
        )
        self._cameras = cameras

    @override
    async def _async_update_data(self) -> dict[str, int | None]:
        """Fetch the signal strength of each camera."""
        token = await self._cameras.async_get_access_token()
        session = async_get_clientsession(self.hass)
        data: dict[str, int | None] = {}
        # The first poll runs before any entity exists; later ones only fetch
        # cameras that have an enabled sensor.
        subscribed = set(self.async_contexts())
        camera_ids = [
            camera_id
            for camera_id in self._cameras.data
            if self.data is None or camera_id in subscribed
        ]
        for camera_id in camera_ids:
            try:
                info = await get_wifi_info(session, token, camera_id)
            except BoschCameraAuthError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="auth_failed"
                ) from err
            except BoschCameraConnectionError, BoschCameraInvalidResponseError:
                # One failing camera must not hide the others; it stays unavailable.
                _LOGGER.debug("Wi-Fi info of camera %s unavailable", camera_id)
                continue
            data[camera_id] = info.signal_strength
        return data
