"""Coordinator for the Bosch Smart Camera integration."""

import asyncio
from collections import defaultdict
from datetime import timedelta
import logging
import time
from typing import override

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
    get_latest_event_image,
    list_cameras,
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
        self._snapshots: dict[str, tuple[float, bytes | None]] = {}
        self._snapshot_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @override
    async def _async_setup(self) -> None:
        """Resolve the OAuth2 implementation."""
        implementation = await async_get_config_entry_implementation(
            self.hass, self.config_entry
        )
        self._oauth_session = OAuth2Session(
            self.hass, self.config_entry, implementation
        )

    @override
    async def _async_update_data(self) -> dict[str, Camera]:
        """Fetch the camera list."""
        await self._oauth_session.async_ensure_token_valid()
        try:
            cameras = await list_cameras(
                async_get_clientsession(self.hass),
                str(self._oauth_session.token[CONF_ACCESS_TOKEN]),
            )
        except BoschCameraAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except (BoschCameraConnectionError, BoschCameraInvalidResponseError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        data = {camera.id: camera for camera in cameras}
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
            await self._oauth_session.async_ensure_token_valid()
            try:
                image = await get_latest_event_image(
                    async_get_clientsession(self.hass),
                    str(self._oauth_session.token[CONF_ACCESS_TOKEN]),
                    camera_id,
                )
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
