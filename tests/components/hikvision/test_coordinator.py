"""Test the request handling of the Hikvision image settings coordinator."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
import threading
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyhik.image import ImageWriteResult
from pyhik.isapi import ISAPIAuthError, ISAPIConnectionError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from homeassistant.components.hikvision import _async_setup_image_settings
from homeassistant.components.hikvision.const import DOMAIN, EVENT_IMAGE_SETTING_CHANGED
from homeassistant.components.hikvision.coordinator import (
    SCAN_INTERVAL,
    async_complete,
    async_run_to_end,
    async_stop_stream,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import Context, CoreState, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

HLC_PATH = "HLC/enabled"


async def _wait_for_waiters(lock: asyncio.Lock, count: int) -> None:
    """Let the loop run until the lock has the given number of waiters.

    Many turns: what comes before can wait for a worker thread, which takes longer
    on a busy machine. No sleeps, so that it works with a frozen clock too.
    """
    for _ in range(100_000):
        if len(lock._waiters or ()) == count:
            return
        await asyncio.sleep(0)
    raise AssertionError(f"{count} waiters expected, got {len(lock._waiters or ())}")


async def _wait_until(event: threading.Event) -> None:
    """Let the loop run until a worker thread has set the event.

    Not in a test that freezes the clock: the sleeps would never end.
    """
    for _ in range(500):
        if event.is_set():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("The worker did not start")


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_queued_behind_the_unload_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a write that gets its turn after the unload does not use the client.

    An action can be waiting for its turn while the entry is unloaded: stopping the
    polling does not stop it, and the client is closed by then.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators

    async with coordinator.lock:
        unload = hass.async_create_task(
            hass.config_entries.async_unload(mock_config_entry.entry_id)
        )
        await _wait_for_waiters(coordinator.lock, 1)
        write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
        await _wait_for_waiters(coordinator.lock, 2)

    assert await unload
    with pytest.raises(HomeAssistantError) as err:
        await write
    assert err.value.translation_key == "image_settings_closed"
    mock_image_settings.set_image_setting.assert_not_called()
    mock_image_settings.close.assert_called_once()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_cancelled_write_keeps_the_client_until_the_request_ends(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the lock is held until a cancelled write has really ended.

    The request runs in a worker thread that cannot be stopped: another request,
    or the unload closing the client, must not use the client at the same time.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _slow_write(path: str, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        return ImageWriteResult(True, 200, "ok")

    mock_image_settings.set_image_setting = _slow_write
    write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
    await _wait_until(started)

    write.cancel()
    for _ in range(10):
        await asyncio.sleep(0)
    # Still running: the client is still in use.
    assert not write.done()
    assert coordinator.lock.locked()

    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await write
    # Once the refresh the write asked for has run too.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not coordinator.lock.locked()


async def test_a_cancelled_write_that_gets_a_401_still_rejects_the_password(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a 401 is dealt with even when the action that sent it was cancelled.

    Otherwise the requests waiting for their turn, and the event stream, would keep
    sending the rejected password, which can lock the account.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()
    writes: list[str] = []

    def _rejected_write(path: str, value: str) -> ImageWriteResult:
        writes.append(value)
        if len(writes) > 1:
            # Would be accepted: only the first one finds the password rejected.
            return ImageWriteResult(True, 200, "ok")
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_image_settings.set_image_setting = _rejected_write
    write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
    await _wait_until(started)
    # Another action waits for its turn.
    queued = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "true"))
    await _wait_for_waiters(coordinator.lock, 1)

    write.cancel()
    for _ in range(10):
        await asyncio.sleep(0)
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await write
    with pytest.raises(HomeAssistantError) as err:
        await queued
    await hass.async_block_till_done(wait_background_tasks=True)

    assert err.value.translation_key == "invalid_auth"
    assert writes == ["false"]
    assert coordinator.credentials_rejected
    mock_hikcamera.return_value.disconnect.assert_called_once()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.parametrize(("status", "rejected"), [(401, True), (403, False)])
async def test_a_cancelled_download_that_gets_a_401_still_rejects_the_password(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    status: int,
    rejected: bool,
) -> None:
    """Test a 401 to a diagnostics request is dealt with though it was cancelled.

    A 403 only refuses that request: the password is not rejected.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _rejected_read() -> str:
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Refused", status)

    request = hass.async_create_task(
        coordinator.async_diagnostics_request(_rejected_read)
    )
    await _wait_until(started)
    request.cancel()
    for _ in range(10):
        await asyncio.sleep(0)
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await request
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.credentials_rejected is rejected
    assert mock_hikcamera.return_value.disconnect.call_count == int(rejected)
    assert [
        flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()
    ] == [SOURCE_REAUTH] * rejected


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_download_the_executor_starts_after_the_stream_is_refused_is_not_sent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a request already handed to a busy executor is not sent once refused.

    The download checked the password before handing the request over; the stream
    had it rejected before the executor started it.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    refused: list[asyncio.Task] = []

    async def _refused_while_queued(*args: Any, **kwargs: Any) -> Any:
        refused.append(hass.async_create_task(coordinator.async_stream_rejected()))
        return await async_run_to_end(*args, **kwargs)

    with (
        patch(
            "homeassistant.components.hikvision.coordinator.async_run_to_end",
            _refused_while_queued,
        ),
        pytest.raises(ISAPIAuthError),
    ):
        await coordinator.async_diagnostics_request(
            mock_image_settings.request_raw, "GET", "/ISAPI/System/deviceInfo"
        )
    await asyncio.gather(*refused)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_image_settings.request_raw.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_waiting_when_the_stream_is_refused_is_not_sent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a write that gets its turn after the stream had the password refused.

    It was waiting before the refusal: it must not send the password again.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators

    async with coordinator.lock:
        write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
        await _wait_for_waiters(coordinator.lock, 1)
        refused = hass.async_create_task(coordinator.async_stream_rejected())
        await _wait_for_waiters(coordinator.lock, 2)

    with pytest.raises(HomeAssistantError) as err:
        await write
    await refused
    await hass.async_block_till_done(wait_background_tasks=True)

    assert err.value.translation_key == "invalid_auth"
    mock_image_settings.set_image_setting.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_refused_write_shows_what_was_switched_off_for_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the entity of a setting switched off to make room shows it at once.

    The camera refused the change itself, so no poll follows.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    hlc = "switch.front_camera_highlight_compensation"
    assert hass.states.get(hlc).state == STATE_ON
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, "badParameters", also_changed={"HLC/enabled": "false"}
    )

    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_setting(
            "Exposure/OverexposeSuppress/enabled", "true"
        )

    assert hass.states.get(hlc).state == STATE_OFF


@pytest.mark.usefixtures("mock_hikcamera")
async def test_each_write_is_logged_with_what_the_camera_answered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the debug log shows each write, then the camera's answer."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    caplog.set_level(logging.DEBUG, "homeassistant.components.hikvision")
    title = mock_config_entry.title

    await coordinator.async_set_setting(HLC_PATH, "false")
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, "badParameters", also_changed={"HLC/enabled": "false"}
    )
    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_setting(
            "Exposure/OverexposeSuppress/enabled", "true"
        )

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert f"{title}: setting {HLC_PATH} to false" in messages
    assert f"{title}: set {HLC_PATH} to false (status 200, ok)" in messages
    assert f"{title}: setting Exposure/OverexposeSuppress/enabled to true" in messages
    assert (
        f"{title}: not set Exposure/OverexposeSuppress/enabled to true "
        "(status 403, badParameters), also changed {'HLC/enabled': 'false'}"
    ) in messages


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_shows_its_value_before_the_poll_that_follows(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the entity shows the new value as soon as the camera took it.

    The poll that follows can be held back by the ones just before.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    hlc = "switch.front_camera_highlight_compensation"
    assert hass.states.get(hlc).state == STATE_ON

    with patch.object(coordinator, "async_request_refresh") as refresh:
        await coordinator.async_set_setting(HLC_PATH, "false")

    refresh.assert_awaited_once()
    assert hass.states.get(hlc).state == STATE_OFF


@pytest.mark.parametrize("fails", [True, False])
async def test_work_finished_for_a_cancelled_caller_logs_only_its_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, fails: bool
) -> None:
    """Test what runs to its end for a cancelled caller reports an error it hits.

    Nothing else would: the caller only sees the cancellation.
    """
    release = asyncio.Event()

    async def _work() -> None:
        await release.wait()
        if fails:
            raise RuntimeError("failed")

    task = hass.async_create_task(async_complete(_work()))
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert ("Error while dealing with a cancelled request" in caplog.text) is fails


async def test_a_job_run_to_end_is_waited_for_when_cancelled_again(
    hass: HomeAssistant,
) -> None:
    """Test a second cancellation does not stop the wait for the job."""
    started = threading.Event()
    finish = threading.Event()
    ended = threading.Event()

    def _job() -> str:
        started.set()
        finish.wait(5)
        ended.set()
        return "done"

    task = hass.async_create_task(async_run_to_end(hass, _job))
    await _wait_until(started)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    for _ in range(10):
        await asyncio.sleep(0)
    assert not task.done()

    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert ended.is_set()


async def test_a_job_run_to_end_returns_its_result(hass: HomeAssistant) -> None:
    """Test the result of a job that is not cancelled is returned."""
    assert await async_run_to_end(hass, lambda value: value * 2, 21) == 42


async def test_a_write_rejected_during_a_reload_does_not_ask_for_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a 401 of a write that ends once shutdown has started starts no reauth.

    The reload may be the one that saved the corrected credentials. The rejection
    is still recorded, so nothing queued sends the old password again.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _rejected_write(path: str, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_image_settings.set_image_setting = _rejected_write
    write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
    await hass.async_add_executor_job(started.wait, 5)

    await coordinator.async_shutdown()
    finish.set()
    with pytest.raises(HomeAssistantError) as err:
        await write
    await hass.async_block_till_done(wait_background_tasks=True)

    assert err.value.translation_key == "invalid_auth"
    assert coordinator.credentials_rejected
    assert not hass.config_entries.flow.async_progress()
    mock_hikcamera.return_value.disconnect.assert_not_called()


async def test_a_poll_rejected_during_a_reload_does_not_ask_for_credentials(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a 401 of a poll that ends once shutdown has started starts no reauth."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _rejected_read() -> dict[str, str]:
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_image_settings.get_image_values = _rejected_read
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_add_executor_job(started.wait, 5)

    await coordinator.async_shutdown()
    finish.set()
    await hass.async_add_executor_job(time.sleep, 0.1)
    for _ in range(20):
        await asyncio.sleep(0)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.credentials_rejected
    assert not isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert not hass.config_entries.flow.async_progress()
    mock_hikcamera.return_value.disconnect.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_rejected_while_the_platforms_unload_does_not_ask_for_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a 401 that comes while the unload waits for the platforms starts no reauth.

    The polling is only shut down after that, so the unload marks the coordinator
    first.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _rejected_write(path: str, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_image_settings.set_image_setting = _rejected_write
    write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
    await hass.async_add_executor_job(started.wait, 5)
    unload_platforms = hass.config_entries.async_unload_platforms_or_raise

    async def _unload_platforms(*args: object) -> None:
        # The write ends while the platforms are being unloaded.
        finish.set()
        with pytest.raises(HomeAssistantError):
            await write
        await unload_platforms(*args)

    with patch.object(
        hass.config_entries, "async_unload_platforms_or_raise", _unload_platforms
    ):
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_failed_unload_still_asks_for_credentials_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test an unload that fails leaves the entry dealing with a 401 as before."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators

    with patch.object(
        hass.config_entries,
        "async_unload_platforms_or_raise",
        side_effect=HomeAssistantError("boom"),
    ):
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert not coordinator.unloading

    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_setting(HLC_PATH, "false")
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_poll_queued_behind_a_rejected_write_during_shutdown_is_skipped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a poll that gets its turn after shutdown began sends nothing.

    A write before it got a 401: the poll must not raise ConfigEntryAuthFailed,
    which would start a reauthentication while the entry reloads.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _rejected_write(path: str, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_image_settings.set_image_setting = _rejected_write
    polls = mock_image_settings.get_image_values.call_count
    write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
    await hass.async_add_executor_job(started.wait, 5)
    # A poll waits for its turn behind the write.
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await _wait_for_waiters(coordinator.lock, 1)

    await coordinator.async_shutdown()
    finish.set()
    with pytest.raises(HomeAssistantError):
        await write
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_image_settings.get_image_values.call_count == polls
    assert not isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert not hass.config_entries.flow.async_progress()


async def test_a_poll_rejected_as_the_unload_begins_does_not_ask_for_credentials(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a 401 whose stream stop overlaps the start of an unload starts no reauth."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators

    def _unload_begins() -> None:
        coordinator.unloading = True

    mock_hikcamera.return_value.disconnect.side_effect = _unload_begins
    mock_image_settings.get_image_values.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_hikcamera.return_value.disconnect.assert_called_once()
    assert not isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert not hass.config_entries.flow.async_progress()


async def test_a_write_rejected_as_the_unload_begins_does_not_ask_for_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a write's 401 whose stream stop overlaps an unload starts no reauth."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators

    def _unload_begins() -> None:
        coordinator.unloading = True

    mock_hikcamera.return_value.disconnect.side_effect = _unload_begins
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_setting(HLC_PATH, "false")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert err.value.translation_key == "invalid_auth"
    assert coordinator.credentials_rejected
    assert not hass.config_entries.flow.async_progress()


async def _unload_that_fails_after(
    hass: HomeAssistant, entry: MockConfigEntry, during: Callable[[], Awaitable[None]]
) -> None:
    """Unload the entry, run something while its platforms unload, then fail."""

    async def _unload_platforms(*args: object) -> None:
        await during()
        raise HomeAssistantError("boom")

    with patch.object(
        hass.config_entries, "async_unload_platforms_or_raise", _unload_platforms
    ):
        await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.FAILED_UNLOAD


@pytest.mark.parametrize("request_kind", ["write", "poll"])
async def test_a_rejection_deferred_by_a_failed_unload_is_dealt_with(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    request_kind: str,
) -> None:
    """Test a 401 that came while the entry was unloading is dealt with if it stays.

    The stream would otherwise keep sending the rejected password.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _rejected(*args: object) -> None:
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Invalid credentials", 401)

    # The request is running when the unload begins.
    if request_kind == "write":
        mock_image_settings.set_image_setting = _rejected
        request = hass.async_create_task(
            coordinator.async_set_setting(HLC_PATH, "false")
        )
    else:
        mock_image_settings.get_image_values = _rejected
        freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
    await hass.async_add_executor_job(started.wait, 5)

    async def _rejected_while_unloading() -> None:
        finish.set()
        if request_kind == "write":
            with pytest.raises(HomeAssistantError):
                await request
        await _wait_for_waiters(coordinator.lock, 0)
        for _ in range(100):
            if coordinator.credentials_rejected and not coordinator.lock.locked():
                break
            await asyncio.sleep(0)
        assert coordinator.credentials_rejected
        # Only recorded so far.
        mock_hikcamera.return_value.disconnect.assert_not_called()
        assert not hass.config_entries.flow.async_progress()

    await _unload_that_fails_after(hass, mock_config_entry, _rejected_while_unloading)

    assert not coordinator.unloading
    mock_hikcamera.return_value.disconnect.assert_called_once()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_deferred_rejection_of_replaced_credentials_is_dropped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test no reauthentication is asked for credentials that were replaced.

    The old stream is still stopped: the reload that would apply the new ones
    failed with the unload, so nothing else replaces it, and it would keep
    sending the rejected password.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    async def _rejected_and_replaced() -> None:
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_setting(HLC_PATH, "false")
        hass.config_entries.async_update_entry(
            mock_config_entry,
            data={**mock_config_entry.data, CONF_PASSWORD: "corrected"},
        )

    await _unload_that_fails_after(hass, mock_config_entry, _rejected_and_replaced)

    assert not coordinator.unloading
    mock_hikcamera.return_value.disconnect.assert_called_once()
    assert not hass.config_entries.flow.async_progress()

    # A refresh afterwards sends nothing, and does not ask for credentials either.
    polls = mock_image_settings.get_image_values.call_count
    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: "switch.front_camera_highlight_compensation"},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_image_settings.get_image_values.call_count == polls
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_an_unload_that_fails_to_stop_the_stream_leaves_the_entry_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a failure after the platforms unloaded does not leave it unloading."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_hikcamera.return_value.disconnect.side_effect = RuntimeError("stuck")

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert not coordinator.unloading
    # The stream stops at the end of the test.
    mock_hikcamera.return_value.disconnect.side_effect = None


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_while_unloading_does_not_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a write that gets through while the entry unloads asks for no poll.

    The poll would only be refused, and make the entities unavailable.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    polls = mock_image_settings.get_image_values.call_count

    coordinator.unloading = True
    await coordinator.async_set_setting(HLC_PATH, "false")
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_image_settings.set_image_setting.assert_called_once_with(HLC_PATH, "false")
    assert coordinator.data[HLC_PATH] == "false"
    assert coordinator.last_update_success
    assert mock_image_settings.get_image_values.call_count == polls
    coordinator.unloading = False


async def test_an_error_while_dealing_with_a_cancelled_job_is_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the handler of a cancelled job's error cannot hide the cancellation."""
    started = threading.Event()
    finish = threading.Event()

    def _job() -> None:
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Invalid credentials", 401)

    async def _broken_handler(err: BaseException) -> None:
        raise RuntimeError("handler failed")

    task = hass.async_create_task(
        async_run_to_end(hass, _job, on_error=_broken_handler)
    )
    await hass.async_add_executor_job(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert "Error while dealing with a cancelled request" in caplog.text


async def test_refreshes_after_a_rejected_poll_send_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the refreshes after a 401 do not send the rejected password again.

    The log says so, once.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.get_image_values.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    polls = mock_image_settings.get_image_values.call_count

    # The polling stops after a rejection; a refresh asked for by hand still comes.
    await async_setup_component(hass, "homeassistant", {})
    for _ in range(2):
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: "switch.front_camera_highlight_compensation"},
            blocking=True,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_image_settings.get_image_values.call_count == polls
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    mock_hikcamera.return_value.disconnect.assert_called_once()
    assert len(hass.config_entries.flow.async_progress()) == 1
    assert [
        record.getMessage()
        for record in caplog.records
        if "nothing more is sent" in record.getMessage()
    ] == [
        f"{mock_config_entry.title} rejected the username or password: nothing "
        "more is sent to it until it is reauthenticated"
    ]


async def test_an_error_resuming_after_a_failed_unload_does_not_hide_its_cause(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the unload's own error is the one reported, and the other is logged."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    async def _rejected_while_unloading() -> None:
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_setting(HLC_PATH, "false")

    with patch.object(
        mock_config_entry, "async_start_reauth", side_effect=RuntimeError("stuck")
    ):
        await _unload_that_fails_after(
            hass, mock_config_entry, _rejected_while_unloading
        )

    assert "Error while resuming" in caplog.text
    assert "boom" in caplog.text


@pytest.mark.parametrize("request_kind", ["write", "poll"])
async def test_a_401_after_the_credentials_were_replaced_asks_for_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    request_kind: str,
) -> None:
    """Test a 401 between saving new credentials and the reload starts no reauth.

    The 401 is about the old credentials of this client, which the reload replaces.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    error = ISAPIAuthError("Invalid credentials", 401)
    mock_image_settings.set_image_setting.side_effect = error
    mock_image_settings.get_image_values.side_effect = error
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_PASSWORD: "corrected"},
    )

    if request_kind == "write":
        # Refused before anything is sent: the old credentials are not used again.
        with pytest.raises(HomeAssistantError) as err:
            await coordinator.async_set_setting(HLC_PATH, "false")
        assert err.value.translation_key == "image_settings_closed"
        mock_image_settings.set_image_setting.assert_not_called()
    else:
        freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert not hass.config_entries.flow.async_progress()
    mock_hikcamera.return_value.disconnect.assert_not_called()


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            ImageWriteResult(True, 200, "ok", also_changed={"WDR/enabled": "false"}),
            {HLC_PATH: "true", "WDR/enabled": "false"},
        ),
        (
            ImageWriteResult(
                False, 403, "refused", also_changed={"WDR/enabled": "false"}
            ),
            {HLC_PATH: "false", "WDR/enabled": "false"},
        ),
    ],
    ids=["accepted", "refused"],
)
@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_cancelled_write_still_shows_what_it_changed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    result: ImageWriteResult,
    expected: dict[str, str],
) -> None:
    """Test what a write changed is shown even when its action was cancelled.

    The camera made the change anyway; with polling disabled nothing else would show
    it. An accepted write is followed by a refresh, once the lock is free.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    coordinator.async_set_updated_data(
        {**coordinator.data, HLC_PATH: "false", "WDR/enabled": "true"}
    )
    started = threading.Event()
    finish = threading.Event()

    def _slow_write(path: str, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        return result

    mock_image_settings.set_image_setting = _slow_write
    polls = mock_image_settings.get_image_values.call_count
    mock_image_settings.get_image_values.return_value = {**coordinator.data, **expected}
    write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "true"))
    await hass.async_add_executor_job(started.wait, 5)

    write.cancel()
    await asyncio.sleep(0)
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await write
    await hass.async_block_till_done(wait_background_tasks=True)

    for path, value in expected.items():
        assert coordinator.data[path] == value
    refreshed = mock_image_settings.get_image_values.call_count > polls
    assert refreshed is result.success


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_cancelled_write_that_fails_still_shows_what_it_switched_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a blocker switched off before a failed request is shown, and logged.

    Also when the action was cancelled while the request ran: the camera is in that
    state anyway.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    events = async_capture_events(hass, EVENT_IMAGE_SETTING_CHANGED)
    started = threading.Event()
    finish = threading.Event()

    def _slow_failing_write(path: str, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        error = ISAPIConnectionError("Cannot connect")
        error.also_changed = {"hlc/ENABLED": "false"}
        raise error

    mock_image_settings.set_image_setting = _slow_failing_write
    write = hass.async_create_task(
        coordinator.async_set_setting("WDR/mode", "open", Context())
    )
    await hass.async_add_executor_job(started.wait, 5)

    write.cancel()
    await asyncio.sleep(0)
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await write
    await hass.async_block_till_done(wait_background_tasks=True)

    # Stored under the setting's own spelling.
    assert coordinator.data[HLC_PATH] == "false"
    assert [e.data["name"] for e in events] == ["Front Camera Highlight compensation"]


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_after_the_credentials_were_replaced_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a write that gets its turn after new credentials were saved sends nothing.

    The old ones would only fail again, and count towards locking the account.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_PASSWORD: "corrected"},
    )

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_setting(HLC_PATH, "false")

    assert err.value.translation_key == "image_settings_closed"
    mock_image_settings.set_image_setting.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_client_made_for_a_cancelled_setup_is_closed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the client still being made when the setup is cancelled gets closed."""
    await setup_integration(hass, mock_config_entry)
    started = threading.Event()
    finish = threading.Event()
    client = MagicMock()

    def _slow_client(*args: object) -> MagicMock:
        started.set()
        finish.wait(5)
        return client

    data = mock_config_entry.data
    # A plain function, so that it runs in the executor like the real class.
    with patch("homeassistant.components.hikvision.ISAPIClient", _slow_client):
        setup = hass.async_create_task(
            _async_setup_image_settings(
                hass,
                mock_config_entry,
                data[CONF_HOST],
                data[CONF_PORT],
                data[CONF_USERNAME],
                data[CONF_PASSWORD],
                data[CONF_SSL],
                True,
                False,
            )
        )
        await hass.async_add_executor_job(started.wait, 5)
        setup.cancel()
        await asyncio.sleep(0)
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await setup

    client.close.assert_called_once()
    client.get_image_settings.assert_not_called()


@pytest.mark.parametrize("request_kind", ["write", "poll"])
async def test_a_rejection_cancelled_while_the_stream_stops_still_completes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    request_kind: str,
) -> None:
    """Test a 401 is fully dealt with when cancelled while the stream is stopped.

    Stopping halfway would leave the entities available and ask for no new
    credentials, while every later write fails.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    error = ISAPIAuthError("Invalid credentials", 401)
    mock_image_settings.set_image_setting.side_effect = error
    mock_image_settings.get_image_values.side_effect = error
    started = threading.Event()
    finish = threading.Event()

    def _slow_disconnect() -> None:
        started.set()
        finish.wait(5)

    mock_hikcamera.return_value.disconnect = _slow_disconnect
    if request_kind == "write":
        request = hass.async_create_task(
            coordinator.async_set_setting(HLC_PATH, "false")
        )
    else:
        freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        request = next(
            task
            for task in asyncio.all_tasks()
            if task.get_name().startswith(f"{coordinator.name} - ")
        )
    await hass.async_add_executor_job(started.wait, 5)

    request.cancel()
    await asyncio.sleep(0)
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await request
    await hass.async_block_till_done(wait_background_tasks=True)

    # New credentials are asked for, and the entities are unavailable, for a poll
    # too.
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert not coordinator.last_update_success
    assert (
        hass.states.get("switch.front_camera_highlight_compensation").state
        == STATE_UNAVAILABLE
    )
    assert coordinator.credentials_rejected
    assert not coordinator.lock.locked()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_an_unload_cancelled_while_a_request_runs_still_closes_the_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the client is closed once the request ends, though the unload is gone."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators

    # A request is running: the unload waits for it before closing the client.
    await coordinator.lock.acquire()
    try:
        unload = hass.async_create_task(
            hass.config_entries.async_unload(mock_config_entry.entry_id)
        )
        await _wait_for_waiters(coordinator.lock, 1)
        unload.cancel()
        await asyncio.sleep(0)
        mock_image_settings.close.assert_not_called()
    finally:
        # Or a failure would leave the teardown waiting for the lock.
        coordinator.lock.release()
    # The release ran to its end: the unload is reported as done, or the entry
    # would stay unloading, unable to load again, until a restart.
    assert await unload is True
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_image_settings.close.assert_called_once()
    assert coordinator.closed
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_a_setup_clean_up_cancelled_halfway_still_stops_the_stream(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the clean-up of a failed setup is not cut short by a cancellation.

    It is cancelled while the client closes; the stream must still be stopped, or its
    thread would keep the process from ending.
    """
    started = threading.Event()
    finish = threading.Event()

    def _slow_close() -> None:
        started.set()
        finish.wait(5)

    mock_image_settings.close = _slow_close
    forward = hass.config_entries.async_forward_entry_setups
    calls = 0

    async def _forward(entry: MockConfigEntry, platforms: list[Platform]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("boom")
        await forward(entry, platforms)

    mock_config_entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_forward_entry_setups", _forward):
        setup = hass.async_create_task(
            hass.config_entries.async_setup(mock_config_entry.entry_id)
        )
        await hass.async_add_executor_job(started.wait, 5)
        setup.cancel()
        await asyncio.sleep(0)
        mock_hikcamera.return_value.disconnect.assert_not_called()
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await setup
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_a_setup_cancelled_while_a_rejected_password_is_dealt_with(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_isapi_client: MagicMock,
) -> None:
    """Test the teardown after a 401 at discovery ends, and is not done twice.

    The setup is cancelled while the stream is stopped: the clean-up that follows
    must not close the client or stop the stream again.
    """
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = ISAPIAuthError("Invalid credentials", 401)
    started = threading.Event()
    finish = threading.Event()
    stops = 0

    def _slow_disconnect() -> None:
        nonlocal stops
        stops += 1
        started.set()
        finish.wait(5)

    mock_hikcamera.return_value.disconnect = _slow_disconnect
    mock_config_entry.add_to_hass(hass)
    setup = hass.async_create_task(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    await hass.async_add_executor_job(started.wait, 5)
    setup.cancel()
    await asyncio.sleep(0)
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await setup
    await hass.async_block_till_done(wait_background_tasks=True)

    client.close.assert_called_once()
    assert stops == 1


async def test_the_stream_stopped_for_a_rejected_password_is_not_stopped_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the unload does not stop a stream a 401 has already stopped."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.get_image_values.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_hikcamera.return_value.disconnect.assert_called_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    mock_hikcamera.return_value.disconnect.assert_called_once()


async def _start_a_slow_stream_stop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> tuple[threading.Event, list[int]]:
    """Have a poll's 401 start stopping the stream, and keep it stopping."""
    started = threading.Event()
    finish = threading.Event()
    stops: list[int] = []

    def _slow_disconnect() -> None:
        stops.append(1)
        started.set()
        finish.wait(5)

    mock_hikcamera.return_value.disconnect = _slow_disconnect
    mock_image_settings.get_image_values.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_add_executor_job(started.wait, 5)
    return finish, stops


async def test_an_unload_during_a_stream_stop_shares_the_disconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test an unload that starts while a 401 stops the stream waits for that stop."""
    await setup_integration(hass, mock_config_entry)
    finish, stops = await _start_a_slow_stream_stop(
        hass, freezer, mock_hikcamera, mock_image_settings
    )

    unload = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    for _ in range(10):
        await asyncio.sleep(0)
    finish.set()
    assert await unload
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(stops) == 1


async def test_home_assistant_stopping_during_a_stream_stop_shares_the_disconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the stop of Home Assistant waits for a stream stop already running."""
    await setup_integration(hass, mock_config_entry)
    finish, stops = await _start_a_slow_stream_stop(
        hass, freezer, mock_hikcamera, mock_image_settings
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    for _ in range(10):
        await asyncio.sleep(0)
    finish.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(stops) == 1


@pytest.mark.usefixtures("mock_hikcamera")
async def test_an_unload_cancelled_while_the_stream_stops_still_closes_the_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the client is closed though the unload is cancelled during the stream stop.

    The platforms are gone by then: the client must not stay open.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _slow_disconnect() -> None:
        started.set()
        finish.wait(5)

    mock_hikcamera.return_value.disconnect = _slow_disconnect
    unload = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    await hass.async_add_executor_job(started.wait, 5)
    unload.cancel()
    await asyncio.sleep(0)
    mock_image_settings.close.assert_not_called()
    finish.set()
    # The release ran to its end: the unload is reported as done, or the entry
    # would stay unloading, unable to load again, until a restart.
    assert await unload is True
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_image_settings.close.assert_called_once()
    assert coordinator.closed
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("platforms_fail", [False, True])
async def test_an_unload_cancelled_while_the_platforms_unload_still_ends(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    platforms_fail: bool,
) -> None:
    """Test an unload cancelled while its platforms unload reports what it did.

    It runs to its end: once the platforms are gone, the stream is stopped and the
    client closed. A CancelledError would leave the entry unloading until a restart.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = asyncio.Event()
    finish = asyncio.Event()
    unload_platforms = hass.config_entries.async_unload_platforms_or_raise

    async def _slow_unload_platforms(*args: Any) -> None:
        started.set()
        await finish.wait()
        if platforms_fail:
            raise HomeAssistantError("stuck")
        await unload_platforms(*args)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms_or_raise",
        _slow_unload_platforms,
    ):
        unload = hass.async_create_task(
            hass.config_entries.async_unload(mock_config_entry.entry_id)
        )
        await started.wait()
        unload.cancel()
        await asyncio.sleep(0)
        finish.set()
        assert await unload is not platforms_fail
    await hass.async_block_till_done(wait_background_tasks=True)

    if platforms_fail:
        # The entry stays loaded, polling, with its stream.
        assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
        assert not coordinator.unloading
        mock_hikcamera.return_value.disconnect.assert_not_called()
        mock_image_settings.close.assert_not_called()
    else:
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
        mock_hikcamera.return_value.disconnect.assert_called_once()
        assert coordinator.closed
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED


def _spy_on_executor_futures(
    hass: HomeAssistant, futures: list[asyncio.Future[Any]]
) -> Callable[..., asyncio.Future[Any]]:
    """Return an async_add_executor_job that keeps the futures it returns."""
    add_job = hass.async_add_executor_job

    def _add_job(target: Callable[..., Any], *args: Any) -> asyncio.Future[Any]:
        future = add_job(target, *args)
        futures.append(future)
        return future

    return _add_job


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_whose_executor_future_is_cancelled_keeps_the_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the lock is held until the worker ends, not until its future is cancelled.

    Home Assistant cancels the futures of executor jobs when it stops, while the
    jobs keep running in their threads.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _slow_write(path: str, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        return ImageWriteResult(True, 200, "ok")

    mock_image_settings.set_image_setting = _slow_write
    futures: list[asyncio.Future[Any]] = []
    with patch.object(
        hass, "async_add_executor_job", _spy_on_executor_futures(hass, futures)
    ):
        write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
        await _wait_until(started)
    assert futures
    # As Home Assistant does when it stops.
    for future in futures:
        future.cancel()
    for _ in range(10):
        await asyncio.sleep(0)
    assert not write.done()
    assert coordinator.lock.locked()

    finish.set()
    await write
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not coordinator.lock.locked()


async def test_the_stream_stop_waits_for_the_thread_though_its_future_is_cancelled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the shared stream stop ends only once the stream is really stopped."""
    await setup_integration(hass, mock_config_entry)
    data = mock_config_entry.runtime_data
    started = threading.Event()
    finish = threading.Event()
    joined = threading.Event()

    def _slow_disconnect() -> None:
        started.set()
        finish.wait(5)
        joined.set()

    mock_hikcamera.return_value.disconnect = _slow_disconnect
    futures: list[asyncio.Future[Any]] = []
    with patch.object(
        hass, "async_add_executor_job", _spy_on_executor_futures(hass, futures)
    ):
        stop = hass.async_create_task(async_stop_stream(hass, data))
        await _wait_until(started)
    assert futures
    for future in futures:
        future.cancel()
    for _ in range(10):
        await asyncio.sleep(0)
    assert not stop.done()
    assert data.stream_stop is not None
    assert not data.stream_stop.done()

    # Another stop waits for the one in progress.
    again = hass.async_create_task(async_stop_stream(hass, data))
    for _ in range(10):
        await asyncio.sleep(0)
    assert not again.done()

    finish.set()
    await stop
    await again
    assert joined.is_set()
    assert not data.stream_stop.cancelled()


async def test_a_job_cancelled_before_it_starts_is_not_run(
    hass: HomeAssistant,
) -> None:
    """Test a job whose executor future is cancelled before it starts never runs.

    Also when its thread picks it up just after the cancellation.
    """
    job = MagicMock()
    queued: list[tuple[asyncio.Future[Any], Callable[[], None]]] = []

    def _not_run_yet(target: Callable[[], None]) -> asyncio.Future[Any]:
        future: asyncio.Future[Any] = hass.loop.create_future()
        queued.append((future, target))
        return future

    with patch.object(hass, "async_add_executor_job", _not_run_yet):
        run = hass.async_create_task(async_run_to_end(hass, job))
        await asyncio.sleep(0)
    future, target = queued[0]
    future.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run
    target()
    job.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_the_close_keeps_the_client_though_its_future_is_cancelled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the coordinator's close holds the lock until the client is closed."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _slow_close() -> None:
        started.set()
        finish.wait(5)

    mock_image_settings.close = _slow_close
    futures: list[asyncio.Future[Any]] = []
    with patch.object(
        hass, "async_add_executor_job", _spy_on_executor_futures(hass, futures)
    ):
        close = hass.async_create_task(coordinator.async_close())
        await _wait_until(started)
    assert futures
    for future in futures:
        future.cancel()
    for _ in range(10):
        await asyncio.sleep(0)
    assert not close.done()
    assert coordinator.lock.locked()

    finish.set()
    await close
    assert not coordinator.lock.locked()


def _executor_that_starts_nothing(
    queued: list[asyncio.Future[Any]],
) -> Callable[..., asyncio.Future[Any]]:
    """Return an async_add_executor_job whose jobs wait for a thread that never comes."""

    def _add_job(target: Callable[..., Any], *args: Any) -> asyncio.Future[Any]:
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        queued.append(future)
        return future

    return _add_job


async def test_a_stream_stop_cancelled_before_it_ran_is_tried_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test a stop whose queued disconnect is cancelled tries again by itself.

    Home Assistant cancels the queued executor jobs when it stops, before its stop
    event: the stop handler waiting for the shared stop must not give up with the
    stream thread still running. The next stop has nothing left to do.
    """
    await setup_integration(hass, mock_config_entry)
    data = mock_config_entry.runtime_data
    disconnect = mock_hikcamera.return_value.disconnect
    disconnect.reset_mock()
    queued: list[asyncio.Future[Any]] = []

    with patch.object(
        hass, "async_add_executor_job", _executor_that_starts_nothing(queued)
    ):
        stop = hass.async_create_task(async_stop_stream(hass, data))
        for _ in range(10):
            await asyncio.sleep(0)
    assert queued
    for future in queued:
        future.cancel()
    # The second attempt gets a thread.
    await stop
    disconnect.assert_called_once()
    assert not data.stream_stop.cancelled()

    await async_stop_stream(hass, data)
    disconnect.assert_called_once()


async def test_a_stream_stop_cancelled_twice_from_within_gives_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the stop is tried again once only, and then cancelled.

    The next stop starts it again.
    """
    await setup_integration(hass, mock_config_entry)
    data = mock_config_entry.runtime_data
    disconnect = mock_hikcamera.return_value.disconnect
    disconnect.reset_mock()
    queued: list[asyncio.Future[Any]] = []

    with patch.object(
        hass, "async_add_executor_job", _executor_that_starts_nothing(queued)
    ):
        stop = hass.async_create_task(async_stop_stream(hass, data))
        for _ in range(10):
            await asyncio.sleep(0)
        queued[0].cancel()
        for _ in range(10):
            await asyncio.sleep(0)
        assert len(queued) == 2
        queued[1].cancel()
        with pytest.raises(asyncio.CancelledError):
            await stop
    disconnect.assert_not_called()

    await async_stop_stream(hass, data)
    disconnect.assert_called_once()


async def test_a_second_stop_that_joined_before_the_cancel_disconnects_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test two stops waiting for a shared stop that is cancelled from within.

    During shutdown the stop handler can join a stop whose queued disconnect Home
    Assistant then cancels. Neither caller may give up with the stream thread still
    running, and the stream is disconnected once: the first to wake starts the stop
    again, and the other waits for that one.
    """
    await setup_integration(hass, mock_config_entry)
    data = mock_config_entry.runtime_data
    disconnect = mock_hikcamera.return_value.disconnect
    disconnect.reset_mock()
    queued: list[asyncio.Future[Any]] = []

    with patch.object(
        hass, "async_add_executor_job", _executor_that_starts_nothing(queued)
    ):
        first = hass.async_create_task(async_stop_stream(hass, data))
        for _ in range(10):
            await asyncio.sleep(0)
        # The second stop joins the first before its disconnect is cancelled.
        second = hass.async_create_task(async_stop_stream(hass, data))
        for _ in range(10):
            await asyncio.sleep(0)
        assert len(queued) == 1
        assert not first.done()
        assert not second.done()
        queued[0].cancel()
    # The new attempt gets a thread.
    await first
    await second

    disconnect.assert_called_once()
    assert data.stream_stop.done()
    assert not data.stream_stop.cancelled()


async def test_a_cancelled_caller_does_not_start_the_stop_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test a caller that is cancelled itself is not kept for another attempt."""
    await setup_integration(hass, mock_config_entry)
    data = mock_config_entry.runtime_data
    disconnect = mock_hikcamera.return_value.disconnect
    disconnect.reset_mock()
    queued: list[asyncio.Future[Any]] = []

    with patch.object(
        hass, "async_add_executor_job", _executor_that_starts_nothing(queued)
    ):
        stop = hass.async_create_task(async_stop_stream(hass, data))
        for _ in range(10):
            await asyncio.sleep(0)
        stop.cancel()
        for _ in range(10):
            await asyncio.sleep(0)
        # The stop it waits for is cancelled from within meanwhile.
        queued[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await stop
    assert len(queued) == 1
    disconnect.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_close_cancelled_before_it_ran_is_still_owed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the client only counts as closed once its close has run."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    close = mock_image_settings.close
    close.reset_mock()
    queued: list[asyncio.Future[Any]] = []

    with patch.object(
        hass, "async_add_executor_job", _executor_that_starts_nothing(queued)
    ):
        closing = hass.async_create_task(coordinator.async_close())
        for _ in range(10):
            await asyncio.sleep(0)
    assert queued
    for future in queued:
        future.cancel()
    with pytest.raises(asyncio.CancelledError):
        await closing
    close.assert_not_called()
    assert not coordinator.closed
    assert not coordinator.lock.locked()

    await coordinator.async_close()
    close.assert_called_once()
    assert coordinator.closed


@pytest.mark.parametrize(
    "failing_step",
    ["unload_platforms", "close"],
)
async def test_a_failed_clean_up_step_does_not_skip_the_others(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    caplog: pytest.LogCaptureFixture,
    failing_step: str,
) -> None:
    """Test every clean-up step of a failed setup runs, and its own error is kept.

    A stream left running would keep the process from ending, and an error while
    cleaning up must not hide that the setup is to be retried.
    """
    forward = hass.config_entries.async_forward_entry_setups
    calls = 0

    async def _forward(entry: MockConfigEntry, platforms: list[Platform]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ConfigEntryNotReady("image platforms not ready")
        await forward(entry, platforms)

    failures = {
        "unload_platforms": patch.object(
            hass.config_entries,
            "async_unload_platforms",
            side_effect=RuntimeError("unload failed"),
        ),
        "close": patch.object(
            mock_image_settings.close, "side_effect", RuntimeError("close failed")
        ),
    }
    mock_config_entry.add_to_hass(hass)
    with (
        patch.object(hass.config_entries, "async_forward_entry_setups", _forward),
        failures[failing_step],
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Error while cleaning up after a failed setup" in caplog.text
    mock_image_settings.close.assert_called_once()
    mock_hikcamera.return_value.disconnect.assert_called_once()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_rejected_while_home_assistant_stops_asks_for_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a 401 of a write that ends while Home Assistant stops starts no reauth.

    Home Assistant's stop only stops the stream: the coordinator is not shut down.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _rejected_write(path: str, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_image_settings.set_image_setting = _rejected_write
    write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
    await _wait_until(started)

    hass.set_state(CoreState.stopping)
    finish.set()
    with pytest.raises(HomeAssistantError):
        await write
    await hass.async_block_till_done(wait_background_tasks=True)
    hass.set_state(CoreState.running)

    assert coordinator.credentials_rejected
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_poll_rejected_while_home_assistant_stops_asks_for_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a 401 of a poll that ends while Home Assistant stops starts no reauth."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _rejected_read() -> dict[str, str]:
        started.set()
        finish.wait(5)
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_image_settings.get_image_values = _rejected_read
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    # Not _wait_until(): its sleeps do not end while the clock is frozen.
    await hass.async_add_executor_job(started.wait, 5)

    hass.set_state(CoreState.stopping)
    finish.set()
    await hass.async_add_executor_job(time.sleep, 0.1)
    for _ in range(20):
        await asyncio.sleep(0)
    await hass.async_block_till_done(wait_background_tasks=True)
    hass.set_state(CoreState.running)

    assert not isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize(
    "cancel", [lambda task: None, asyncio.Task.cancel], ids=["finished", "cancelled"]
)
@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_that_ends_while_home_assistant_stops_does_not_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    cancel: Callable[[asyncio.Task[None]], object],
) -> None:
    """Test a write that ends while Home Assistant stops asks for no refresh.

    Also when it was cancelled: the refresh would only send another request.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    polls = mock_image_settings.get_image_values.call_count
    started = threading.Event()
    finish = threading.Event()

    def _slow_write(path: str, value: str) -> ImageWriteResult:
        started.set()
        finish.wait(5)
        return ImageWriteResult(True, 200, "ok")

    mock_image_settings.set_image_setting = _slow_write
    write = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
    await _wait_until(started)

    hass.set_state(CoreState.stopping)
    cancel(write)
    finish.set()
    await asyncio.wait([write])
    await hass.async_block_till_done(wait_background_tasks=True)
    hass.set_state(CoreState.running)

    assert coordinator.data[HLC_PATH] == "false"
    assert mock_image_settings.get_image_values.call_count == polls


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_queued_while_home_assistant_stops_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a write waiting for the lock sends nothing once Home Assistant stops.

    The one already sent still ends, and shows what it changed.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()
    sent: list[str] = []

    def _slow_write(path: str, value: str) -> ImageWriteResult:
        sent.append(value)
        started.set()
        finish.wait(5)
        return ImageWriteResult(True, 200, "ok")

    mock_image_settings.set_image_setting = _slow_write
    first = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "false"))
    await _wait_until(started)
    queued = hass.async_create_task(coordinator.async_set_setting(HLC_PATH, "true"))
    await _wait_for_waiters(coordinator.lock, 1)

    hass.set_state(CoreState.stopping)
    finish.set()
    await first
    with pytest.raises(HomeAssistantError) as err:
        await queued
    await hass.async_block_till_done(wait_background_tasks=True)
    hass.set_state(CoreState.running)

    assert err.value.translation_key == "image_settings_closed"
    assert sent == ["false"]
    assert coordinator.data[HLC_PATH] == "false"


async def test_a_failed_stream_stop_after_a_rejected_write_still_asks_for_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an error stopping the stream keeps the 401's error and its reauth.

    With polling disabled, nothing else would ask for new credentials.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    mock_hikcamera.return_value.disconnect.side_effect = RuntimeError("stuck")

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_setting(HLC_PATH, "false")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert err.value.translation_key == "invalid_auth"
    assert "Error stopping the event stream after rejected credentials" in caplog.text
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    # The unload stops the stream again, once it works.
    mock_hikcamera.return_value.disconnect.side_effect = None
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_hikcamera.return_value.disconnect.call_count == 2


@pytest.mark.parametrize("sub_status", ["HLCMutexWDROrDehaze", "WDROrDehazeMutexHLC"])
@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_conflict_on_another_setting_shows_the_cameras_code(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    sub_status: str,
) -> None:
    """Test the conflict messages are only used for the settings in the conflict.

    A write to anything else did not turn highlight compensation, WDR or defog on.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, sub_status
    )

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_setting("Color/brightnessLevel", "60")

    assert err.value.translation_key == "image_setting_refused"
    assert err.value.translation_placeholders == {"code": sub_status}


@pytest.mark.parametrize(
    ("path", "value", "sub_status", "key"),
    [
        # Turning highlight compensation on while WDR or defog is on, in any
        # spelling of the path or the value.
        ("HLC/enabled", "true", "WDROrDehazeMutexHLC", "image_setting_conflict_wdr"),
        ("hlc/HLCMode", "open", "WDROrDehazeMutexHLC", "image_setting_conflict_wdr"),
        # Turning WDR or defog on while highlight compensation is on.
        ("WDR/mode", "open", "HLCMutexWDROrDehaze", "image_setting_conflict_hlc"),
        ("WDR/mode", "auto", "HLCMutexWDROrDehaze", "image_setting_conflict_hlc"),
        (
            "Dehaze/DehazeMode",
            "OPEN",
            "HLCMutexWDROrDehaze",
            "image_setting_conflict_hlc",
        ),
        # Turning one off: the message would tell to turn something off first.
        ("HLC/enabled", "false", "WDROrDehazeMutexHLC", "image_setting_refused"),
        ("WDR/mode", "close", "HLCMutexWDROrDehaze", "image_setting_refused"),
        # Firmware that sends the code of the other side: the message follows the
        # setting that was turned on.
        ("WDR/mode", "open", "WDROrDehazeMutexHLC", "image_setting_conflict_hlc"),
        ("HLC/enabled", "true", "HLCMutexWDROrDehaze", "image_setting_conflict_wdr"),
        # Another conflict code says nothing about these two.
        ("HLC/enabled", "true", "otherMutex", "image_setting_refused"),
    ],
)
@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_conflict_message_fits_the_setting_and_its_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    path: str,
    value: str,
    sub_status: str,
    key: str,
) -> None:
    """Test the conflict messages are only used for the write they describe.

    Each code says which side was being turned on. Anything else gets the
    camera's code.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, sub_status
    )

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_setting(path, value)

    assert err.value.translation_key == key


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_conflict_whose_blocker_was_switched_off_shows_the_cameras_code(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a refusal after the camera switched the blocker off is not about it.

    Telling to turn WDR off first would be wrong: it is off already.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, "WDROrDehazeMutexHLC", also_changed={"WDR/mode": "close"}
    )

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_setting("HLC/enabled", "true")

    assert err.value.translation_key == "image_setting_refused"


async def test_a_worker_that_starts_just_after_a_cancel_sends_nothing(
    hass: HomeAssistant,
) -> None:
    """Test a job cancelled before its worker started is not run.

    Future.cancel() marks the future at once, but the queued job only hears of it
    on a later turn of the loop: a worker can start in between.
    """
    job = MagicMock()
    queued: list[tuple[asyncio.Future[Any], Callable[[], None]]] = []

    def _not_run_yet(target: Callable[[], None]) -> asyncio.Future[Any]:
        future: asyncio.Future[Any] = hass.loop.create_future()
        queued.append((future, target))
        return future

    with patch.object(hass, "async_add_executor_job", _not_run_yet):
        run = hass.async_create_task(async_run_to_end(hass, job))
        await asyncio.sleep(0)
    future, target = queued[0]
    future.cancel()
    # The worker starts before the loop has run anything since the cancel.
    target()
    job.assert_not_called()
    with pytest.raises(asyncio.CancelledError):
        await run


async def test_a_rejection_after_an_unload_that_closed_the_client_is_dealt_with(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a 401 deferred by an unload whose stream stop failed still asks again.

    The unload closes the client, and shuts the coordinator down, even when the
    stream could not be stopped: the entry stays loaded, its stream still sending
    the rejected password.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    mock_hikcamera.return_value.disconnect.side_effect = [RuntimeError("stuck"), None]

    async def _rejected_while_unloading(*args: object) -> None:
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_setting(HLC_PATH, "false")
        # Only recorded so far.
        assert not hass.config_entries.flow.async_progress()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms_or_raise",
        _rejected_while_unloading,
    ):
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert coordinator.closed
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert mock_hikcamera.return_value.disconnect.call_count == 2
    # The credentials were not replaced: the reauthentication asks for them.
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"restart_required_{mock_config_entry.entry_id}"
        )
        is None
    )


async def test_the_stream_is_stopped_again_when_the_reload_with_new_credentials_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a stream that could not be stopped is stopped again by a failed reload.

    The first stop fails, and reauthentication starts all the same. The reload
    that applies the new credentials then fails to stop it too: the old stream,
    still sending the rejected password, is stopped again, without a new flow.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    disconnect = mock_hikcamera.return_value.disconnect
    disconnect.side_effect = [RuntimeError("stuck"), RuntimeError("stuck"), None]

    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_setting(HLC_PATH, "false")
    await hass.async_block_till_done(wait_background_tasks=True)
    (flow,) = hass.config_entries.flow.async_progress()
    assert disconnect.call_count == 1

    await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    # The reload's own stop, then the one after the failed unload.
    assert disconnect.call_count == 3
    assert not hass.config_entries.flow.async_progress()
    # The flow said it worked: the restart the new credentials wait for is asked
    # for by a repair issue.
    issue = issue_registry.async_get_issue(
        DOMAIN, f"restart_required_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "restart_required"
    # It goes with the entry.
    assert issue.config_entry_id == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("changes", "asked"),
    [
        pytest.param({CONF_HOST: "192.0.2.2"}, True, id="host"),
        pytest.param({CONF_PORT: 8080}, True, id="port"),
        pytest.param({CONF_SSL: True}, True, id="ssl"),
        pytest.param({CONF_VERIFY_SSL: False}, True, id="verify_ssl"),
        pytest.param({CONF_PASSWORD: "new-password"}, True, id="password"),
        pytest.param({}, False, id="unchanged"),
    ],
)
@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_saved_settings_that_a_failed_unload_holds_back_need_a_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    changes: dict[str, object],
    asked: bool,
) -> None:
    """Test any connection setting a flow saved asks for a restart if not applied.

    The flow saves them, then reloads the entry; when the unload fails, the entry
    keeps what it was set up with until a restart.
    """
    await setup_integration(hass, mock_config_entry)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, **changes}
    )

    with patch.object(
        hass.config_entries,
        "async_unload_platforms_or_raise",
        side_effect=HomeAssistantError("stuck"),
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)

    issue = issue_registry.async_get_issue(
        DOMAIN, f"restart_required_{mock_config_entry.entry_id}"
    )
    assert (issue is not None) is asked


async def test_new_credentials_after_a_failed_unload_need_a_restart(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the reauth flow after a failed unload saves and asks for a restart.

    Home Assistant does not reload an entry whose unload failed, so the flow
    must not say it was reloaded.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    async def _rejected() -> None:
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_setting(HLC_PATH, "false")

    await _unload_that_fails_after(hass, mock_config_entry, _rejected)
    (flow,) = hass.config_entries.flow.async_progress()
    # The stream sending the rejected password is stopped all the same.
    mock_hikcamera.return_value.disconnect.assert_called_once()

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_restart_required"
    assert mock_config_entry.data[CONF_USERNAME] == "new-user"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert "OperationNotAllowed" not in caplog.text
    # Nothing is sent with the rejected or the new password until the restart.
    mock_image_settings.get_image_values.reset_mock()
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_image_settings.get_image_values.assert_not_called()
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize("stop_fails", [True, False])
async def test_a_rejection_deferred_by_a_cancelled_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    stop_fails: bool,
) -> None:
    """Test a 401 deferred by an unload cancelled during the stream stop.

    If the stop then fails, the entry stays loaded, its stream still sending the
    rejected password: new credentials are asked for, and the stream stopped again.
    If it works, the entry is gone, and nothing is asked for.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    started = threading.Event()
    finish = threading.Event()
    stops = 0

    def _disconnect() -> None:
        nonlocal stops
        stops += 1
        if stops == 1:
            started.set()
            finish.wait(5)
            if stop_fails:
                raise RuntimeError("stuck")

    mock_hikcamera.return_value.disconnect = _disconnect

    async def _rejected_while_unloading(*args: object) -> None:
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_setting(HLC_PATH, "false")
        # Only recorded so far.
        assert not hass.config_entries.flow.async_progress()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms_or_raise",
        _rejected_while_unloading,
    ):
        unload = hass.async_create_task(
            hass.config_entries.async_unload(mock_config_entry.entry_id)
        )
        await hass.async_add_executor_job(started.wait, 5)
        unload.cancel()
        await asyncio.sleep(0)
        finish.set()
        # What the release did is what the unload reports.
        assert await unload is not stop_fails
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.closed
    flows = hass.config_entries.flow.async_progress()
    if stop_fails:
        assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
        assert not coordinator.unloading
        assert len(flows) == 1
        assert flows[0]["context"]["source"] == SOURCE_REAUTH
        assert stops == 2
    else:
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
        assert not flows
        assert stops == 1


async def test_a_rejection_deferred_by_an_unload_as_home_assistant_stops_is_dropped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a failed unload while Home Assistant stops asks for no credentials."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    async def _rejected_while_unloading() -> None:
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_setting(HLC_PATH, "false")
        hass.set_state(CoreState.stopping)

    await _unload_that_fails_after(hass, mock_config_entry, _rejected_while_unloading)
    hass.set_state(CoreState.running)

    assert coordinator.credentials_rejected
    assert not hass.config_entries.flow.async_progress()
    mock_hikcamera.return_value.disconnect.assert_not_called()


@pytest.mark.parametrize("meanwhile", ["stopping", "replaced"])
async def test_a_deferred_rejection_called_off_while_the_stream_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
    meanwhile: str,
) -> None:
    """Test the recovery after a failed unload asks for nothing it no longer needs.

    Home Assistant began to stop, or new credentials were saved, while the stream
    was being stopped.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    def _change() -> None:
        if meanwhile == "stopping":
            hass.set_state(CoreState.stopping)
        else:
            hass.config_entries.async_update_entry(
                mock_config_entry,
                data={**mock_config_entry.data, CONF_PASSWORD: "corrected"},
            )

    mock_hikcamera.return_value.disconnect.side_effect = lambda: (
        hass.loop.call_soon_threadsafe(_change)
    )

    async def _rejected_while_unloading() -> None:
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_setting(HLC_PATH, "false")

    await _unload_that_fails_after(hass, mock_config_entry, _rejected_while_unloading)
    hass.set_state(CoreState.running)

    mock_hikcamera.return_value.disconnect.assert_called_once()
    assert not hass.config_entries.flow.async_progress()


async def test_a_deferred_rejection_of_replaced_credentials_as_home_assistant_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a failed unload as Home Assistant stops leaves the stream to its stop."""
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    async def _rejected_and_replaced() -> None:
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_setting(HLC_PATH, "false")
        hass.config_entries.async_update_entry(
            mock_config_entry,
            data={**mock_config_entry.data, CONF_PASSWORD: "corrected"},
        )
        hass.set_state(CoreState.stopping)

    await _unload_that_fails_after(hass, mock_config_entry, _rejected_and_replaced)
    hass.set_state(CoreState.running)

    mock_hikcamera.return_value.disconnect.assert_not_called()
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_refused_write_after_a_failed_poll_keeps_the_entities_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test what a refused write switched off does not count as a successful poll.

    Only those values are known: the others are stale since the poll failed.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.get_image_values.side_effect = ISAPIConnectionError("timeout")
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not coordinator.last_update_success
    assert (
        hass.states.get("switch.front_camera_highlight_compensation").state
        == STATE_UNAVAILABLE
    )
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, "badParameters", also_changed={"HLC/enabled": "false"}
    )

    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_setting(
            "Exposure/OverexposeSuppress/enabled", "true"
        )
    await hass.async_block_till_done()

    assert coordinator.data["HLC/enabled"] == "false"
    assert not coordinator.last_update_success
    assert (
        hass.states.get("switch.front_camera_highlight_compensation").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_write_after_a_failed_poll_waits_for_a_poll_to_be_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a write that worked does not count as a successful poll either.

    Only what it changed is known. The refresh that follows it makes the entities
    available again, once a poll works.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    values = dict(mock_image_settings.get_image_values.return_value)
    mock_image_settings.get_image_values.side_effect = ISAPIConnectionError("timeout")
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        hass.states.get("switch.front_camera_highlight_compensation").state
        == STATE_UNAVAILABLE
    )

    # What the write itself leaves, before the refresh that follows it.
    with patch.object(coordinator, "async_request_refresh", AsyncMock()) as refresh:
        await coordinator.async_set_setting("HLC/enabled", "false")
        await hass.async_block_till_done()
    refresh.assert_called_once()

    assert coordinator.data["HLC/enabled"] == "false"
    assert not coordinator.last_update_success
    assert (
        hass.states.get("switch.front_camera_highlight_compensation").state
        == STATE_UNAVAILABLE
    )

    # The camera answers again.
    mock_image_settings.get_image_values.side_effect = None
    mock_image_settings.get_image_values.return_value = {
        **values,
        "HLC/enabled": "false",
    }
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator.last_update_success
    assert hass.states.get("switch.front_camera_highlight_compensation").state == "off"
