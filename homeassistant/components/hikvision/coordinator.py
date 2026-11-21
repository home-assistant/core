"""Coordinator for the image settings of a Hikvision camera."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from pyhik.image import PRIVILEGE_SUB_STATUSES, ImageSetting, ImageWriteResult
from pyhik.isapi import ISAPIAuthError, ISAPIClient, ISAPIConnectionError, ISAPIError

from homeassistant.components.logbook import async_log_entry
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import HikvisionConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

# The platforms with an entity for an image setting

# The sub status codes with which a camera refuses a setting that another one excludes.
# Which of the two is meant depends on the firmware: some use one code for both
# directions, others one code for each, so the message follows the setting that was
# asked for, not the code.
_CONFLICT_SUB_STATUSES = frozenset({"HLCMutexWDROrDehaze", "WDROrDehazeMutexHLC"})


def _conflict_key(path: str) -> str:
    """Return the message for a setting refused because another one excludes it."""
    if path.lower().startswith("hlc/"):
        return "image_setting_conflict_wdr"
    return "image_setting_conflict_hlc"


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
        # The settings, in lowercase, that this setup has an entity for, including
        # the disabled ones. Not what is left in the entity registry from an earlier
        # setup: a setting that is no longer accepted may still have an entry there.
        self.entity_paths: set[str] = set()
        # The platform of the entity that this setup has added for a setting. A
        # firmware that changes a select into a sensor leaves both in the registry.
        self.entity_platforms: dict[str, str] = {}
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

    async def async_set_setting(
        self, path: str, value: str, context: Context | None = None
    ) -> None:
        """Write one setting and update the stored values.

        The context is that of the action that asked for the change.
        """
        await self._async_write(
            self.client.set_image_setting, (path, value), {path: value}, path, context
        )

    async def async_set_linked_setting(
        self, setting: ImageSetting, value: str, context: Context | None = None
    ) -> None:
        """Write a mode that also controls an enabled flag, such as BLC."""
        enabled = "false" if value == setting.off_value else "true"
        updates = {setting.path: value}
        if setting.linked_enabled_path:
            updates[setting.linked_enabled_path] = enabled
        await self._async_write(
            self.client.set_image_linked_setting,
            (setting, value),
            updates,
            setting.path,
            context,
        )

    async def _async_write(
        self,
        method: Callable[..., ImageWriteResult],
        args: tuple[Any, ...],
        updates: dict[str, str],
        path: str,
        context: Context | None,
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
        # The camera may have had to switch other settings off first.
        others = (
            self._async_report_also_changed(path, result.also_changed, context)
            if result.also_changed
            else {}
        )
        if not result.success:
            if others:
                self.async_set_updated_data({**self.data, **others})
            # The English description from the library is not part of the message,
            # only the code of the device is.
            placeholders = {"code": result.sub_status}
            if result.sub_status in _CONFLICT_SUB_STATUSES and not others:
                # If the camera switched the blocker off first, and still refused,
                # the blocker is no longer the reason.
                key = _conflict_key(path)
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
        self.async_set_updated_data({**self.data, **others, **updates})
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

    def _async_report_also_changed(
        self, path: str, also_changed: dict[str, str], context: Context | None
    ) -> dict[str, str]:
        """Tell the user about settings that were changed to make room.

        Writes a logbook entry for each of them and returns their new values,
        keyed like the stored values.
        """
        # The spelling of a path as the integration knows it, from the settings it
        # discovered and the values it has, so that a setting that was missing from
        # the last poll is still stored under the key its entity reads.
        keys = {key.lower(): key for key in self.data}
        for setting in self.settings:
            keys[setting.path.lower()] = setting.path
            if setting.linked_enabled_path:
                keys.setdefault(
                    setting.linked_enabled_path.lower(), setting.linked_enabled_path
                )
        requested = self._async_entity_name(path)[0]
        known: dict[str, str] = {}
        for other_path, value in also_changed.items():
            name, entity_id = self._async_entity_name(other_path)
            action = (
                "turned off"
                if value.lower() in ("false", "close")
                else f"set to {value}"
            )
            message = f"was {action} automatically so that {requested} could be changed"
            async_log_entry(
                self.hass,
                name,
                message,
                # With an entity the entry takes the domain, and so the icon, of its
                # entity.
                domain=None if entity_id else DOMAIN,
                entity_id=entity_id,
                context=context,
            )
            known[keys.get(other_path.lower(), other_path)] = value
        return known

    def _async_entity_name(self, path: str) -> tuple[str, str | None]:
        """Return the name and entity ID of the entity for a setting, if any.

        A mode that comes with an enabled flag, such as BLC, has one entity, for the
        mode: the camera reports the flag when it turns the feature off.
        """
        for setting in self.settings:
            if (
                setting.linked_enabled_path
                and setting.linked_enabled_path.lower() == path.lower()
            ):
                path = setting.path
                break
        if (domain := self.entity_platforms.get(path.lower())) is None:
            # Not an entity of this setup: the registry may still hold one from an
            # earlier setup, which is no longer there to link to.
            return path, None
        device_id = self.config_entry.runtime_data.device_id
        unique_id = f"{device_id}_image_{path.lower()}"
        registry = er.async_get(self.hass)
        if (entity_id := registry.async_get_entity_id(domain, DOMAIN, unique_id)) and (
            entry := registry.async_get(entity_id)
        ):
            state = self.hass.states.get(entity_id)
            name = state.name if state else entry.name or entry.original_name
            return name or path, entity_id
        return path, None
