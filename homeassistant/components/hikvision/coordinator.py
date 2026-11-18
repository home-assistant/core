"""Coordinator for the image settings of a Hikvision camera."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from pyhik.image import PRIVILEGE_SUB_STATUSES, ImageSetting, ImageWriteResult
from pyhik.isapi import ISAPIAuthError, ISAPIClient, ISAPIConnectionError, ISAPIError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import HikvisionConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

# The sub status codes with which a camera refuses a setting that another one excludes
_CONFLICT_KEYS = {
    "HLCMutexWDROrDehaze": "image_setting_conflict_hlc",
    "WDROrDehazeMutexHLC": "image_setting_conflict_wdr",
}


class HikvisionImageCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Poll the current image settings and write changes to the camera."""

    config_entry: HikvisionConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HikvisionConfigEntry,
        client: ISAPIClient,
        settings: list[ImageSetting],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} image settings",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.settings = settings
        # A write reads the whole document, edits it and sends it back, so it must
        # not overlap with another request on the same client.
        self.lock = asyncio.Lock()
        # Set under the lock by the first 401, and kept for the life of this client:
        # a request queued behind it must not send the rejected password again, as
        # repeated attempts can lock the account. A reload makes a new client.
        self.credentials_rejected = False

    @override
    async def _async_update_data(self) -> dict[str, str]:
        """Fetch the current values."""
        try:
            async with self.lock:
                if self.credentials_rejected:
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN, translation_key="invalid_auth"
                    )
                try:
                    return await self.hass.async_add_executor_job(
                        self.client.get_image_values
                    )
                except ISAPIAuthError as err:
                    if err.status_code == 401:
                        self.credentials_rejected = True
                    raise
        except ISAPIError as err:
            if isinstance(err, ISAPIAuthError) and err.status_code == 401:
                await self._async_stop_stream()
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="invalid_auth"
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="image_settings_update_failed",
            ) from err

    async def _async_stop_stream(self) -> None:
        """Stop the event stream, which would keep using the rejected password.

        Repeated attempts with a wrong password can lock the account.
        """
        await self.hass.async_add_executor_job(
            self.config_entry.runtime_data.camera.disconnect
        )

    async def async_set_setting(self, path: str, value: str) -> None:
        """Write one setting and update the stored values."""
        await self._async_write(
            self.client.set_image_setting, (path, value), {path: value}
        )

    async def async_set_linked_setting(self, setting: ImageSetting, value: str) -> None:
        """Write a mode that also controls an enabled flag, such as BLC."""
        enabled = "false" if value == setting.off_value else "true"
        updates = {setting.path: value}
        if setting.linked_enabled_path:
            updates[setting.linked_enabled_path] = enabled
        await self._async_write(
            self.client.set_image_linked_setting, (setting, value), updates
        )

    async def _async_write(
        self,
        method: Callable[..., ImageWriteResult],
        args: tuple[Any, ...],
        updates: dict[str, str],
    ) -> None:
        """Run a write in the executor and update the stored values."""
        try:
            async with self.lock:
                if self.credentials_rejected:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN, translation_key="invalid_auth"
                    )
                try:
                    result = await self.hass.async_add_executor_job(method, *args)
                except ISAPIAuthError as err:
                    if err.status_code == 401:
                        self.credentials_rejected = True
                    raise
        except ISAPIError as err:
            raise await self._async_write_error(err) from err
        if not result.success:
            # The English description from the library is not part of the message,
            # only the code of the device is.
            placeholders = {"code": result.sub_status}
            if result.sub_status in _CONFLICT_KEYS:
                key = _CONFLICT_KEYS[result.sub_status]
            elif (
                result.status_code == 403
                and result.sub_status in PRIVILEGE_SUB_STATUSES
            ):
                key = "image_setting_not_allowed"
            else:
                key = "image_setting_refused"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders=placeholders,
            )
        self.async_set_updated_data({**self.data, **updates})
        await self.async_request_refresh()

    async def _async_write_error(self, err: ISAPIError) -> HomeAssistantError:
        """Return the translated error for a write the device did not take."""
        if isinstance(err, ISAPIAuthError) and err.status_code == 401:
            # Do not wait for the next poll, it would send the rejected password
            # again, and a debounced refresh may not run at all.
            await self._async_stop_stream()
            await self.async_shutdown()
            self.async_set_update_error(
                ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="invalid_auth"
                )
            )
            self.config_entry.async_start_reauth(self.hass)
            key = "invalid_auth"
        elif isinstance(err, ISAPIAuthError):
            key = "image_setting_not_allowed"
        elif isinstance(err, ISAPIConnectionError):
            key = "cannot_connect"
        else:
            key = "image_setting_error"
        return HomeAssistantError(translation_domain=DOMAIN, translation_key=key)
