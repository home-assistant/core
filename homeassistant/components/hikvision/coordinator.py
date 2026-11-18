"""Coordinator for the image settings of a Hikvision camera."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, override

from pyhik.image import PRIVILEGE_SUB_STATUSES, ImageSetting, ImageWriteResult
from pyhik.isapi import ISAPIAuthError, ISAPIClient, ISAPIConnectionError, ISAPIError

from homeassistant.components.logbook import async_log_entry
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntryState,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import HikvisionConfigEntry, HikvisionData

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
# How long to wait before asking for new credentials again, when a form of the entry
# was open and Home Assistant did not start the flow
REAUTH_RETRY_INTERVAL = timedelta(minutes=1)
# The cameras of an NVR share one client and one lock, so they are polled one after
# the other. A slower poll keeps a write from waiting behind dozens of reads.
NVR_SCAN_INTERVAL = timedelta(minutes=5)

# The platforms with an entity for an image setting


def _read_outcome(task: asyncio.Future[Any]) -> None:
    """Mark the outcome of a task as read, so that asyncio does not report it."""
    if not task.cancelled():
        task.exception()


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


def entry_is_current(entry: HikvisionConfigEntry, data: Any) -> bool:
    """Return whether the runtime data is still the one of a loaded entry.

    What was started by one setup may end after the entry was unloaded, or after a
    reload has made a new setup: it must not act on the new one, which has its own
    stream, client and credentials.
    """
    return getattr(entry, "runtime_data", None) is data and entry.state in (
        ConfigEntryState.LOADED,
        ConfigEntryState.SETUP_IN_PROGRESS,
        # An unload that failed leaves the setup running, with its platforms
        ConfigEntryState.FAILED_UNLOAD,
    )


async def async_run_alone[_T](
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    lock: asyncio.Lock,
    request: Callable[[], _T],
) -> _T:
    """Run a request of the setup on the client, alone, as the coordinators do.

    The lock stays taken until the executor job has really ended, even if the setup
    is cancelled, so that nothing closes the client under it.
    """
    await lock.acquire()

    async def _run() -> _T:
        try:
            return await hass.async_add_executor_job(request)
        finally:
            lock.release()

    try:
        task = entry.async_create_task(hass, _run(), "hikvision image discovery")
    except BaseException:
        lock.release()
        raise
    task.add_done_callback(_read_outcome)
    if not task.done():
        await asyncio.wait([task])
    return task.result()


async def async_reject_credentials(
    hass: HomeAssistant, entry: HikvisionConfigEntry, *, lock_held: bool = False
) -> None:
    """Stop everything that would send the rejected password again.

    Repeated attempts with a wrong password can lock the account. The event stream
    keeps trying, and so do the coordinators of an NVR, which share the login.
    Reauthentication reloads the entry, which starts them again.

    The caller holds the lock of the image client, or not: a request that is running
    must end before the coordinators are made unavailable, or its result would make
    one available again.
    """
    data = entry.runtime_data
    if data.image_credentials_rejected:
        # The event stream, or a request, found it first and is dealing with it.
        return
    # Before the first await, so that nothing sends the password while it is stopped.
    data.image_credentials_rejected = True
    await hass.async_add_executor_job(data.camera.disconnect)
    error = ConfigEntryAuthFailed(
        translation_domain=DOMAIN, translation_key="invalid_auth"
    )
    if lock_held or not data.image_coordinators:
        await _async_stop_coordinators(data.image_coordinators, error)
    else:
        async with data.image_coordinators[0].lock:
            await _async_stop_coordinators(data.image_coordinators, error)
    if not entry_is_current(entry, data):
        # The entry was unloaded, or reloaded, while this was stopping things.
        return
    _async_start_reauth(hass, entry)


@callback
def _async_start_reauth(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Ask for new credentials, as soon as Home Assistant can.

    Home Assistant does not start a flow while another one of the entry is open, a
    form to reconfigure it for example. If that form is closed without a change,
    nothing would ask again, and the entry would stay stopped. So this tries again
    until the flow is there. Saving the form reloads the entry, which ends this.
    """
    entry.async_start_reauth(hass)
    if any(entry.async_get_active_flows(hass, {SOURCE_REAUTH})):
        return
    cancel: Callable[[], None] | None = None

    @callback
    def _retry(_now: datetime) -> None:
        nonlocal cancel
        if any(entry.async_get_active_flows(hass, {SOURCE_RECONFIGURE})):
            return
        entry.async_start_reauth(hass)
        if cancel is not None:
            cancel()
            cancel = None

    cancel = async_track_time_interval(hass, _retry, REAUTH_RETRY_INTERVAL)

    @callback
    def _stop() -> None:
        if cancel is not None:
            cancel()

    entry.async_on_unload(_stop)


async def _async_stop_coordinators(
    coordinators: list[HikvisionImageCoordinator], error: ConfigEntryAuthFailed
) -> None:
    """Stop polling, and make the entities of the coordinators unavailable."""
    for coordinator in coordinators:
        await coordinator.async_shutdown()
        coordinator.async_set_update_error(error)


class HikvisionImageCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Poll the current image settings and write changes to the camera.

    A standalone camera has one coordinator (``channel`` is None). An NVR has
    one per attached camera, reached through the NVR's proxy endpoints, and they
    share the client and its lock.
    """

    config_entry: HikvisionConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HikvisionConfigEntry,
        client: ISAPIClient,
        settings: list[ImageSetting],
        channel: int | None = None,
        lock: asyncio.Lock | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=(
                f"{DOMAIN} image settings"
                if channel is None
                else f"{DOMAIN} image settings channel {channel}"
            ),
            update_interval=SCAN_INTERVAL if channel is None else NVR_SCAN_INTERVAL,
        )
        self.client = client
        self.settings = settings
        self.channel = channel
        # What to pass to the client to reach this camera: nothing for a
        # standalone camera, the NVR's channel ID and its proxy for an attached one.
        self._target: dict[str, Any] = (
            {} if channel is None else {"channel": channel, "proxy": True}
        )
        # A write reads the whole document, edits it and sends it back, so it must
        # not overlap with another request on the same client. The coordinators of
        # an NVR share one client, so they share the lock too.
        self.lock = lock if lock is not None else asyncio.Lock()
        # The settings, in lowercase, that this setup has an entity for, including
        # the disabled ones. Not what is left in the entity registry from an earlier
        # setup: a setting that is no longer accepted may still have an entry there.
        self.entity_paths: set[str] = set()
        # The platform of the entity that this setup has added for a setting. A
        # firmware that changes a select into a sensor leaves both in the registry.
        self.entity_platforms: dict[str, str] = {}
        # Set when the entry is unloading: a request that was queued must not use
        # the client, which is about to be closed, or the runtime data, which goes.
        self.closed = False

    @property
    def unique_id_prefix(self) -> str:
        """Return what the unique IDs of this camera's entities start with."""
        device_id = self.config_entry.runtime_data.device_id
        if self.channel is None:
            return f"{device_id}_image_"
        return f"{device_id}_{self.channel}_image_"

    @override
    async def _async_update_data(self) -> dict[str, str]:
        """Fetch the current values."""
        # The setup this poll belongs to: it may end after another one has begun.
        data = self.config_entry.runtime_data
        try:
            values = await self.async_request(
                partial(self.client.get_image_values, **self._target)
            )
        except ISAPIError as err:
            if (
                isinstance(err, ISAPIAuthError)
                and err.status_code == 401
                # Raising it asks for new credentials for the whole entry.
                and entry_is_current(self.config_entry, data)
            ):
                # The request has already stopped everything that would send the
                # password again.
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="invalid_auth"
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="image_settings_update_failed",
            ) from err
        if data.image_credentials_rejected and entry_is_current(
            self.config_entry, data
        ):
            # The event stream was refused while this was running, and made the
            # entities unavailable. A result must not make them available again.
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            )
        return values

    async def async_request[_T](
        self,
        request: Callable[[], _T],
        done: Callable[[_T | None, ISAPIError | None], None] | None = None,
    ) -> _T:
        """Run a request on the device, alone on the client.

        An executor job cannot be cancelled. If the caller is, a service call that
        is stopped for example, the lock must stay taken until the request has
        really ended, or the next one would use the client at the same time. The
        request therefore runs in a task of the entry that the caller only waits
        for. A caller that is still waiting for its turn is cancelled with it, and
        the request is never sent.

        ``done`` is called with the result, or the error, in that task: what the
        camera did must be recorded even if the caller is gone.
        """
        await self.lock.acquire()
        if self.closed:
            self.lock.release()
            raise ISAPIConnectionError("The entry is being unloaded")
        # The setup this request belongs to: it may end after another one has begun.
        data = self.config_entry.runtime_data
        if data.image_credentials_rejected:
            # A request that was waiting for the lock must not send the password
            # again after another one found it rejected.
            self.lock.release()
            raise ISAPIAuthError("The credentials were rejected", 401)
        try:
            task = self.config_entry.async_create_task(
                self.hass, self._async_run(request, done, data), f"{self.name} request"
            )
        except BaseException:
            self.lock.release()
            raise
        # A caller that was cancelled does not read the outcome.
        task.add_done_callback(_read_outcome)
        if not task.done():
            # Waiting for it, unlike awaiting it, does not cancel it with the caller.
            await asyncio.wait([task])
        return task.result()

    async def _async_run[_T](
        self,
        request: Callable[[], _T],
        done: Callable[[_T | None, ISAPIError | None], None] | None,
        data: HikvisionData,
    ) -> _T:
        """Run a request, and deal with what comes of it, holding the lock."""
        try:
            try:
                result = await self.hass.async_add_executor_job(request)
            except ISAPIError as err:
                if done is not None:
                    done(None, err)
                if (
                    isinstance(err, ISAPIAuthError)
                    and err.status_code == 401
                    # A request that outlived its setup must not reject the
                    # credentials of the one that replaced it.
                    and entry_is_current(self.config_entry, data)
                ):
                    # Before the lock is released: what waits for it must not send
                    # the password again.
                    await async_reject_credentials(
                        self.hass, self.config_entry, lock_held=True
                    )
                raise
            if done is not None:
                done(result, None)
            return result
        finally:
            self.lock.release()

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

        def done(result: ImageWriteResult | None, err: ISAPIError | None) -> None:
            """Record what the camera did, whoever is still waiting for it."""
            # The camera may have switched other settings off first, even if the
            # request that followed failed.
            also_changed = (
                result.also_changed
                if result is not None
                else err.also_changed
                if err is not None
                else {}
            )
            changed = (
                self._async_report_also_changed(path, also_changed, context)
                if also_changed
                else {}
            )
            if result is not None and result.success:
                changed = {**changed, **updates}
            if changed:
                self.async_set_updated_data({**self.data, **changed})

        try:
            result = await self.async_request(
                partial(method, *args, **self._target), done
            )
        except ISAPIError as err:
            raise self._write_error(err) from err
        if not result.success:
            # The English description from the library is not part of the message,
            # only the code of the device is.
            placeholders = {"code": result.sub_status}
            if result.sub_status in _CONFLICT_SUB_STATUSES and not result.also_changed:
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
        await self.async_request_refresh()

    def _write_error(self, err: ISAPIError) -> HomeAssistantError:
        """Return the translated error for a write the device did not take."""
        if isinstance(err, ISAPIAuthError) and err.status_code == 401:
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
        unique_id = f"{self.unique_id_prefix}{path.lower()}"
        registry = er.async_get(self.hass)
        if (entity_id := registry.async_get_entity_id(domain, DOMAIN, unique_id)) and (
            entry := registry.async_get(entity_id)
        ):
            state = self.hass.states.get(entity_id)
            name = state.name if state else entry.name or entry.original_name
            return name or path, entity_id
        return path, None
