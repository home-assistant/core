"""Coordinator for the Bosch Smart Home Camera integration."""

from datetime import timedelta
import logging
from typing import override

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
    list_cameras,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config_flow import DOMAIN

_LOGGER = logging.getLogger(__name__)

# The camera list only changes when the user adds or removes a camera.
SCAN_INTERVAL = timedelta(minutes=5)

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
        self._remove_stale_devices(data)
        return data

    def _remove_stale_devices(self, cameras: dict[str, Camera]) -> None:
        """Remove devices of cameras that are no longer part of the account."""
        device_registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            if not any(
                domain == DOMAIN and camera_id in cameras
                for domain, camera_id in device.identifiers
            ):
                device_registry.async_remove_device(device.id)
