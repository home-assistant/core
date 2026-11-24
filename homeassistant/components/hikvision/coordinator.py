"""Coordinator for the image settings of a Hikvision camera."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import contextlib
from datetime import timedelta
from functools import partial
import logging
import threading
from typing import TYPE_CHECKING, Any, override

from pyhik.image import PRIVILEGE_SUB_STATUSES, ImageSetting, ImageWriteResult
from pyhik.isapi import ISAPIAuthError, ISAPIClient, ISAPIConnectionError, ISAPIError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import HikvisionConfigEntry, HikvisionData

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

# The sub status codes with which a camera refuses a setting that another one excludes
# Highlight compensation cannot be on together with WDR or defog. Each code says
# which side was being turned on, and its message only fits a write that turns
# that side on, as in pyHik's own handling: for anything else, turning one off
# or another setting, the camera's code is shown.
_CONFLICT_KEYS = {
    # WDR or defog is on: highlight compensation cannot be turned on.
    "WDROrDehazeMutexHLC": (
        "image_setting_conflict_wdr",
        frozenset({"hlc/enabled", "hlc/hlcmode"}),
    ),
    # Highlight compensation is on: WDR or defog cannot be turned on.
    "HLCMutexWDROrDehaze": (
        "image_setting_conflict_hlc",
        frozenset({"wdr/mode", "dehaze/dehazemode"}),
    ),
}
# What the camera writes to turn one of them off: the flag, or the mode.
_OFF_VALUES = frozenset({"false", "close", "off"})


def _conflict_key(sub_status: str | None, writes: dict[str, str]) -> str | None:
    """Return the message for a conflict the writes ran into, if one fits.

    Firmware does not agree on which of the two codes it sends: the message is
    chosen from the setting that was turned on, whichever code came with it.
    """
    if sub_status not in _CONFLICT_KEYS:
        return None
    for key, paths in _CONFLICT_KEYS.values():
        if any(
            path.lower() in paths and value.lower() not in _OFF_VALUES
            for path, value in writes.items()
        ):
            return key
    return None


def _async_done(future: asyncio.Future[Any]) -> asyncio.Future[None]:
    """Return a future that is done when the given one is, and can be cancelled."""
    done: asyncio.Future[None] = future.get_loop().create_future()

    def _set_done(_: asyncio.Future[Any]) -> None:
        if not done.done():
            done.set_result(None)

    future.add_done_callback(_set_done)
    return done


async def _async_wait_to_end(awaitable: asyncio.Future[Any]) -> None:
    """Wait for a future to end, through any cancellation of the caller."""
    while not awaitable.done():
        try:
            await _async_done(awaitable)
        except asyncio.CancelledError:
            # Cancelled again: it is still running, so keep waiting.
            continue


async def async_complete[_T](
    awaitable: Coroutine[Any, Any, _T] | asyncio.Future[_T],
) -> _T:
    """Run something to its end even if the caller is cancelled meanwhile.

    The cancellation is passed on once it has ended: what deals with a rejected
    password must not stop halfway, with the stream stopped but no new credentials
    asked for.
    """
    if isinstance(awaitable, asyncio.Future):
        # Shared with others: each of them waits for the same one.
        task = awaitable
    else:
        # Started at once: it often ends without waiting, like a plain await would.
        task = asyncio.eager_task_factory(asyncio.get_running_loop(), awaitable)
    try:
        if not task.done():
            await _async_done(task)
    except asyncio.CancelledError:
        await _async_wait_to_end(task)
        if not task.cancelled() and task.exception() is not None:
            _LOGGER.error(
                "Error while dealing with a cancelled request",
                exc_info=task.exception(),
            )
        raise
    return task.result()


def _async_add_tracked_job[_T](
    hass: HomeAssistant, job: Callable[..., _T], *args: Any
) -> asyncio.Future[_T]:
    """Run a job in the executor, and return a future that only the job ends.

    The future of the executor can be cancelled by others, Home Assistant cancels
    them when it stops, while the job keeps running in its thread: the client must
    not be released, or closed, under it. This one is done when the job is, with
    its result or error, or cancelled if the job never started.
    """
    loop = asyncio.get_running_loop()
    ended: asyncio.Future[_T] = loop.create_future()
    state = threading.Lock()
    started = False
    abandoned = False
    # Set once the executor future is known: the worker can start before
    # async_add_executor_job has even returned.
    registered = threading.Event()
    executor_future: asyncio.Future[None] | None = None

    def _end(outcome: Callable[[], object]) -> None:
        if not ended.done():
            outcome()

    def _report(outcome: Callable[[], object]) -> None:
        # A closed loop raises: nothing waits any more.
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(_end, outcome)

    def _run() -> None:
        nonlocal started, abandoned
        registered.wait()
        with state:
            # Future.cancel() marks the future cancelled at once, but the queued job
            # only hears of it, as _executor_done does, on a later turn of the loop:
            # a worker that starts in between must not send the request either.
            # Reading the state of the future from here is a plain attribute read.
            if abandoned or (
                executor_future is not None and executor_future.cancelled()
            ):
                abandoned = True
                return
            started = True
        try:
            result = job(*args)
        except BaseException as err:  # noqa: BLE001
            _report(partial(ended.set_exception, err))
        else:
            _report(partial(ended.set_result, result))

    def _executor_done(future: asyncio.Future[None]) -> None:
        nonlocal abandoned
        if not future.cancelled():
            return
        with state:
            if started:
                # Running anyway: it reports when it ends.
                return
            abandoned = True
        _end(ended.cancel)

    try:
        executor_future = hass.async_add_executor_job(_run)
    finally:
        registered.set()
    executor_future.add_done_callback(_executor_done)
    return ended


async def async_run_to_end[_T](
    hass: HomeAssistant,
    job: Callable[..., _T],
    *args: Any,
    on_error: Callable[[BaseException], Awaitable[None]] | None = None,
    on_result: Callable[[_T], Awaitable[None]] | None = None,
) -> _T:
    """Run a job in the executor, and wait for it to end even if cancelled.

    An executor job cannot be stopped: a caller that is cancelled while it runs
    must not release the lock of the client, or close the client, under it. The
    cancellation is passed on once the job has ended.

    The caller does not see what the job did once it is cancelled, so ``on_error``
    is given what it raised, or ``on_result`` what it returned, first, and is run
    to its end as well: a rejected password must still be dealt with, and a change
    the device made must still be shown.
    """
    future = _async_add_tracked_job(hass, job, *args)
    try:
        if not future.done():
            # Not the future itself: awaiting it would cancel it with the caller.
            await _async_done(future)
    except asyncio.CancelledError:
        await _async_wait_to_end(future)
        handling: Awaitable[None] | None = None
        if future.cancelled():
            pass
        elif (err := future.exception()) is not None:
            if on_error is not None:
                handling = on_error(err)
        elif on_result is not None:
            handling = on_result(future.result())
        if handling is not None:
            handler = asyncio.ensure_future(handling)
            await _async_wait_to_end(handler)
            if not handler.cancelled() and handler.exception() is not None:
                _LOGGER.error(
                    "Error while dealing with a cancelled request",
                    exc_info=handler.exception(),
                )
        raise
    return future.result()


async def async_stop_stream(hass: HomeAssistant, data: HikvisionData) -> None:
    """Stop the event stream of a setup, once.

    Several paths stop it (a rejected password, a failed setup, the unload, Home
    Assistant stopping), and they can overlap: they all wait for the same stop,
    which runs to its end even if one of them is cancelled. Only a stop that
    failed, or was cancelled before the disconnect could run, is tried again.
    """

    async def _async_disconnect() -> None:
        # Until the thread of the stream has really been joined.
        await async_run_to_end(hass, data.camera.disconnect)

    # Once more if the stop is cancelled from within: Home Assistant cancels the
    # queued executor jobs when it stops, before its stop event, so a disconnect
    # still waiting for a thread is cancelled without having run, and the stream
    # thread, which keeps the process from ending, would be left running.
    for attempt in range(2):
        task = data.stream_stop
        if task is None or (
            task.done() and (task.cancelled() or task.exception() is not None)
        ):
            task = data.stream_stop = asyncio.eager_task_factory(
                asyncio.get_running_loop(), _async_disconnect()
            )
        try:
            await async_complete(task)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if (
                attempt == 0
                and task.cancelled()
                # Not this caller being cancelled: that is passed on.
                and (current is None or not current.cancelling())
            ):
                continue
            raise
        return


def log_credentials_rejected(entry: HikvisionConfigEntry) -> None:
    """Say that nothing is retried: the next request is the user's to make."""
    _LOGGER.warning(
        "%s rejected the username or password: nothing more is sent to it until "
        "it is reauthenticated",
        entry.title,
    )


def _describe(updates: dict[str, str]) -> str:
    """Return the settings of a write as the logs give them."""
    return ", ".join(f"{path} to {value}" for path, value in updates.items())


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
        # The camera may spell a path in its values otherwise than in its
        # capabilities, which the entities and the writes use: the values are
        # stored under that spelling, so that each setting has one value.
        self._spellings: dict[str, str] = {}
        for setting in settings:
            for path in (setting.path, setting.linked_enabled_path):
                if path is not None:
                    self._spellings.setdefault(path.lower(), path)
        # A write reads the whole document, edits it and sends it back, so it must
        # not overlap with another request on the same client.
        self.lock = asyncio.Lock()
        # The settings, in lowercase, that this setup has an entity for, including
        # the disabled ones. Not what is left in the entity registry from an earlier
        # setup: a setting that is no longer accepted may still have an entry there.
        self.entity_paths: set[str] = set()
        # Set under the lock by the first 401, and kept for the life of this client:
        # a request queued behind it must not send the rejected password again, as
        # repeated attempts can lock the account. A reload makes a new client.
        self.credentials_rejected = False
        # Set under the lock when the client is closed: a request that was queued,
        # such as an action waiting for its turn, must not use it.
        self.closed = False
        # Set by the unload before its first await, and cleared again if it fails: a
        # request that ends meanwhile must not ask for credentials, which the reload
        # that unloads this may just have replaced.
        self.unloading = False

    @override
    async def _async_update_data(self) -> dict[str, str]:
        """Fetch the current values."""
        try:
            async with self.lock:
                # A poll that was queued must not run once the entry is unloading,
                # nor raise ConfigEntryAuthFailed for a rejection found meanwhile:
                # that would start a reauthentication during the reload.
                if self.closed or self._stopping:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="image_settings_closed",
                    )
                if self.credentials_rejected:
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN, translation_key="invalid_auth"
                    )
                return self._as_settings_spell(
                    await self._async_send(self.client.get_image_values)
                )
        except ISAPIError as err:
            if (
                isinstance(err, ISAPIAuthError)
                and err.status_code == 401
                # A poll that ends while the entry is unloading, or reloading with
                # new credentials, must not ask for them again.
                and not self._stopping
            ):
                # To its end even if this poll is cancelled meanwhile: a stopped
                # stream with no reauthentication would leave the entry stuck.
                await async_complete(self._async_poll_rejected())
                if not self._stopping:
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN, translation_key="invalid_auth"
                    ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="image_settings_update_failed",
            ) from err

    def _as_settings_spell(self, values: dict[str, str]) -> dict[str, str]:
        """Return the values with each path spelled as its setting spells it.

        A path no setting has is kept as the camera sends it. If the camera sends a
        path both ways, the setting's own spelling wins.
        """
        spelled: dict[str, str] = {}
        for path, value in values.items():
            key = self._spellings.get(path.lower(), path)
            if path == key or key not in spelled:
                spelled[key] = value
        return spelled

    @property
    def _stopping(self) -> bool:
        """Return whether this client is stopping, or its credentials were replaced.

        Home Assistant stopping counts too.

        Once new credentials are saved, a reload replaces this client: a 401 it gets
        meanwhile is about the old ones, and must not ask for credentials again.
        """
        # Home Assistant stopping does not shut the coordinator down first: its
        # stop listener only stops the stream. A refresh or a reauthentication
        # started now would only reach a camera, or a user, Home Assistant is
        # leaving.
        if self.hass.is_stopping or self.unloading or self._shutdown_requested:
            return True
        return self._credentials_replaced

    @property
    def _recovery_called_off(self) -> bool:
        """Return whether a deferred rejection no longer needs dealing with.

        Home Assistant is stopping, or new credentials were saved: the reload that
        applies them makes a new client and a new stream.
        """
        return self.hass.is_stopping or self._credentials_replaced

    @property
    def _credentials_replaced(self) -> bool:
        """Return whether the entry no longer has the credentials of this client."""
        data = self.config_entry.runtime_data
        stored = self.config_entry.data
        return (stored[CONF_USERNAME], stored[CONF_PASSWORD]) != (
            data.username,
            data.password,
        )

    async def _async_send[_T](
        self,
        job: Callable[..., _T],
        *args: Any,
        on_result: Callable[[_T], Awaitable[None]] | None = None,
    ) -> _T:
        """Send a request to the camera. The caller holds the lock.

        A 401 is recorded before the lock is released, also when the caller was
        cancelled while the request ran: what waits for the lock must not send the
        rejected password again.
        """
        try:
            return await async_run_to_end(
                self.hass,
                job,
                *args,
                on_error=self._async_cancelled_request_failed,
                on_result=on_result,
            )
        except ISAPIAuthError as err:
            if err.status_code == 401:
                self.credentials_rejected = True
            raise

    async def _async_cancelled_request_failed(self, err: BaseException) -> None:
        """Deal with the error of a request whose caller was cancelled."""
        if isinstance(err, ISAPIAuthError) and err.status_code == 401:
            await self._async_reject_credentials()

    async def _async_poll_rejected(self) -> None:
        """Stop the stream after a poll got a 401, and ask for new credentials.

        Raising ConfigEntryAuthFailed would do the rest too, but not if the poll is
        cancelled meanwhile: so the entities are made unavailable and the credentials
        asked for here. Asking twice opens a single flow.
        """
        await self._async_stop_stream()
        # The unload may have begun while the stream was stopping.
        if not self._stopping:
            # Published here too, not only by the error the poll raises after this:
            # a cancelled poll raises nothing, and the entities would stay available.
            self.async_set_update_error(
                ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="invalid_auth"
                )
            )
            log_credentials_rejected(self.config_entry)
            self.config_entry.async_start_reauth(self.hass)

    async def _async_reject_credentials(
        self, *, after_failed_unload: bool = False
    ) -> None:
        """Stop everything that would send the rejected password, and ask for one.

        Do not wait for the next poll, it would send the rejected password again,
        and a debounced refresh may not run at all.

        A request that ends once the coordinator is shutting down, because the entry
        is unloading or reloading with new credentials, only records the rejection:
        asking for credentials again would start a flow for ones already replaced.

        After a failed unload the coordinator may be shut down and closed already,
        while the entry stays loaded with the rejected credentials: then only Home
        Assistant stopping, or credentials replaced meanwhile, call the recovery off.
        """
        self.credentials_rejected = True

        def _called_off() -> bool:
            if after_failed_unload:
                return self._recovery_called_off
            return self._stopping

        if _called_off():
            return
        await self._async_stop_stream()
        if _called_off():
            # The unload began while the stream was stopping.
            return
        await self.async_shutdown()
        self.async_set_update_error(
            ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            )
        )
        log_credentials_rejected(self.config_entry)
        self.config_entry.async_start_reauth(self.hass)

    async def async_unload_failed(self) -> None:
        """Carry on after an unload that failed, and left the entry loaded.

        A 401 that came while it was unloading was only recorded. If the entry still
        has the credentials that were rejected, the stream would keep sending them,
        so what the 401 calls for is done now. If they were replaced, no new flow is
        asked for, but the stream is still stopped: the reload that would apply the
        new ones failed with this unload, so nothing else replaces the old stream,
        which would keep sending the rejected password and could lock the account.
        """
        self.unloading = False
        # Not _stopping: the unload may have shut the coordinator down and closed
        # the client before it failed, and the stream may still be sending the
        # rejected password. Even once reauthentication has started: the stop before
        # it may have failed, and the reload with the new credentials is then the one
        # that failed.
        if not self.credentials_rejected or self.hass.is_stopping:
            return
        if self._credentials_replaced:
            await async_complete(self._async_stop_stream())
            return
        await async_complete(self._async_reject_credentials(after_failed_unload=True))

    async def async_close(self) -> None:
        """Stop the polling and close the client, once no request is using it."""
        await self.async_shutdown()
        async with self.lock:
            if not self.closed:

                async def _async_close_now() -> None:
                    await async_run_to_end(self.hass, self.client.close)
                    # Only once it is closed: a close cancelled before it ran is
                    # still owed.
                    self.closed = True

                await async_complete(_async_close_now())

    async def _async_stop_stream(self) -> None:
        """Stop the event stream, which would keep using the rejected password.

        Repeated attempts with a wrong password can lock the account. An error here
        does not stop the rest of the recovery: without new credentials the entry
        would stay stuck. The stop is tried again by the next one, such as the reload
        that applies them.
        """
        try:
            await async_stop_stream(self.hass, self.config_entry.runtime_data)
        except Exception:
            _LOGGER.exception(
                "Error stopping the event stream after rejected credentials"
            )

    async def async_diagnostics_request[_T](
        self, job: Callable[..., _T], *args: Any
    ) -> _T:
        """Send a request for the diagnostics, as a poll or a write is sent.

        One request at a time on the client, waited for to its end even if the
        download is cancelled, and not sent once this client is closing, or its
        credentials were rejected or replaced. Raises HomeAssistantError then.

        A 401 the job raises as an ISAPIAuthError is dealt with as for a write:
        the stream is stopped and new credentials are asked for.
        """
        try:
            async with self.lock:
                if self.closed or self.credentials_rejected or self._stopping:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="image_settings_closed",
                    )
                return await self._async_send(job, *args)
        except ISAPIAuthError as err:
            if err.status_code == 401:
                await async_complete(self._async_reject_credentials())
            raise

    async def async_read_values(self) -> dict[str, str]:
        """Read the current values for the diagnostics, spelled as a poll spells them.

        Sent as async_diagnostics_request sends a request: the cached values are
        stale when no entity listens, as the coordinator does not poll then.
        """
        return self._as_settings_spell(
            await self.async_diagnostics_request(self.client.get_image_values)
        )

    @property
    def _device_name(self) -> str:
        """Return the name of the camera, as the logs give it."""
        return self.config_entry.title

    async def async_set_setting(self, path: str, value: str) -> None:
        """Write one setting and update the stored values."""
        await self._async_write(
            self.client.set_image_setting, (path, value), {path: value}
        )

    async def async_set_linked_setting(self, setting: ImageSetting, value: str) -> None:
        """Write a mode that also controls an enabled flag, such as BLC."""
        updates = {setting.path: value}
        if setting.linked_enabled_path:
            updates[setting.linked_enabled_path] = (
                "false" if value == setting.off_value else "true"
            )
        await self._async_write(
            self.client.set_image_linked_setting, (setting, value), updates
        )

    async def _async_write(
        self,
        method: Callable[..., ImageWriteResult],
        args: tuple[Any, ...],
        updates: dict[str, str],
    ) -> None:
        """Send a write to the camera and store what it changed."""
        try:
            async with self.lock:
                # Once new credentials are saved, a queued action must not send the
                # old ones: the reload that applies them is coming. Nor start a
                # request once Home Assistant is stopping; one already sent ends.
                if self.closed or self.hass.is_stopping or self._credentials_replaced:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="image_settings_closed",
                    )
                if self.credentials_rejected:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN, translation_key="invalid_auth"
                    )
                _LOGGER.debug("%s: setting %s", self._device_name, _describe(updates))
                result = await self._async_send(
                    method,
                    *args,
                    on_result=partial(self._async_cancelled_write_done, updates),
                )
        except ISAPIError as err:
            raise await self._async_write_error(err) from err
        if error := self._apply_write_result(updates, result):
            raise error
        if not self._stopping:
            # Not while unloading: the poll would only be refused.
            await self.async_request_refresh()

    async def _async_cancelled_write_done(
        self, updates: dict[str, str], result: ImageWriteResult
    ) -> None:
        """Show what a write did when the action that asked for it was cancelled.

        The device made the change anyway, and with polling disabled nothing else
        would ever show it. The lock is still held here, so the refresh that
        follows a write is only started, to run once it is released.
        """
        if not self._apply_write_result(updates, result) and not self._stopping:
            self.config_entry.async_create_background_task(
                self.hass, self.async_request_refresh(), f"{self.name} refresh"
            )

    def _apply_write_result(
        self, updates: dict[str, str], result: ImageWriteResult
    ) -> HomeAssistantError | None:
        """Store what a write changed, and return the error to raise if refused."""
        _LOGGER.debug(
            "%s: %s %s (status %s, %s)%s",
            self._device_name,
            "set" if result.success else "not set",
            _describe(updates),
            result.status_code,
            result.sub_status,
            f", also changed {result.also_changed}" if result.also_changed else "",
        )
        # The camera may have had to switch other settings off first, even when it
        # then refused the change itself: show them as they are on the camera.
        others = self._as_settings_spell(result.also_changed)
        if not result.success:
            if others:
                # Only these are known, and no poll follows a refused write: not
                # async_set_updated_data, which would also count the write as a
                # successful refresh, making the entities available again with
                # stale values after a failed poll, and reschedule the polling.
                self.data = {**self.data, **others}
                self.async_update_listeners()
            # The English description from the library is not part of the message,
            # only the code of the device is.
            placeholders = {"code": result.sub_status}
            if not others and (
                # A linked write also sets the enabled flag of its mode.
                conflict := _conflict_key(result.sub_status, updates)
            ):
                # If the camera switched the blocker off first, and still refused,
                # the blocker is no longer the reason.
                key = conflict
            elif (
                result.status_code == 403
                and result.sub_status in PRIVILEGE_SUB_STATUSES
            ):
                key = "image_setting_not_allowed"
            else:
                key = "image_setting_refused"
            return HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders=placeholders,
            )
        # Not async_set_updated_data either: only what the write changed is known,
        # and after a failed poll the other values are stale. The refresh that
        # follows a write makes the entities available again, once it works.
        self.data = {**self.data, **others, **updates}
        self.async_update_listeners()
        return None

    async def _async_write_error(self, err: ISAPIError) -> HomeAssistantError:
        """Return the translated error for a write the device did not take."""
        if isinstance(err, ISAPIAuthError) and err.status_code == 401:
            await async_complete(self._async_reject_credentials())
            key = "invalid_auth"
        elif isinstance(err, ISAPIAuthError):
            key = "image_setting_not_allowed"
        elif isinstance(err, ISAPIConnectionError):
            key = "cannot_connect"
        else:
            key = "image_setting_error"
        return HomeAssistantError(translation_domain=DOMAIN, translation_key=key)
