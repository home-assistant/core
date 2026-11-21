"""Test the requests the Hikvision coordinator makes to the camera."""

import asyncio
import copy
from datetime import timedelta
import threading
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyhik.image import ImageWriteResult
from pyhik.isapi import ISAPIAuthError, ISAPIConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.hikvision import STREAM_CREDENTIALS_ID
from homeassistant.components.hikvision.coordinator import (
    SCAN_INTERVAL,
    async_reject_credentials,
    async_run_alone,
    entry_is_current,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

BRIGHTNESS = "Color/brightnessLevel"


class SlowCamera:
    """A client whose write takes as long as the test wants, in the executor.

    The executor only runs a function that is not a mock for real, so this is
    installed in place of the mocked method.
    """

    def __init__(
        self,
        error: Exception | None = None,
        result: ImageWriteResult | None = None,
    ) -> None:
        """Initialize the camera."""
        self.started = threading.Event()
        self.release = threading.Event()
        self.writes: list[tuple[str, str]] = []
        self._error = error
        self._result = result or ImageWriteResult(True, 200, "ok")

    def set_image_setting(self, path: str, value: str) -> ImageWriteResult:
        """Write a setting, when the test lets it end."""
        self.writes.append((path, value))
        self.started.set()
        assert self.release.wait(5)
        if self._error is not None:
            raise self._error
        return self._result

    async def wait_until_started(self) -> None:
        """Wait for the write, without using the executor it is holding."""
        async with asyncio.timeout(5):
            while not self.started.is_set():
                await asyncio.sleep(0)


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_cancelled_write_keeps_the_client_until_it_ends(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the next request waits for a request that is still running.

    The camera is still working on a write whose caller was stopped, and a client
    must not be used by two requests at the same time.
    """
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    camera = SlowCamera()
    mock_image_settings.set_image_setting = camera.set_image_setting

    first = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "10"))
    await camera.wait_until_started()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    # The camera has not finished, so the client is still taken.
    assert coordinator.lock.locked()
    second = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "20"))
    await asyncio.sleep(0.05)
    assert not second.done()
    assert camera.writes == [(BRIGHTNESS, "10")]

    camera.release.set()
    await second
    await hass.async_block_till_done()

    assert not coordinator.lock.locked()
    assert camera.writes == [(BRIGHTNESS, "10"), (BRIGHTNESS, "20")]


@pytest.mark.usefixtures("mock_hikcamera")
async def test_the_error_of_a_cancelled_write_is_not_left_unread(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a request that failed after its caller was stopped is not reported."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    camera = SlowCamera(TimeoutError("slow camera"))
    mock_image_settings.set_image_setting = camera.set_image_setting

    task = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "10"))
    await camera.wait_until_started()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    camera.release.set()
    await hass.async_block_till_done()

    assert "never retrieved" not in caplog.text
    assert not coordinator.lock.locked()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_unload_waits_for_a_request_that_is_running(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the client is not closed under a request that is still running."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    camera = SlowCamera()
    mock_image_settings.set_image_setting = camera.set_image_setting

    write = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "10"))
    await camera.wait_until_started()
    write.cancel()

    unload = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    await asyncio.sleep(0.05)
    mock_image_settings.close.assert_not_called()

    camera.release.set()
    assert await unload
    mock_image_settings.close.assert_called_once()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_request_that_is_still_queued_is_cancelled_with_its_caller(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a write that has not started is not sent after its caller was stopped."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    camera = SlowCamera()
    mock_image_settings.set_image_setting = camera.set_image_setting

    first = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "10"))
    await camera.wait_until_started()
    queued = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "20"))
    await asyncio.sleep(0.05)
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued

    camera.release.set()
    await first
    await hass.async_block_till_done()

    # Only what had already started was sent, and the client is free again.
    assert camera.writes == [(BRIGHTNESS, "10")]
    assert not coordinator.lock.locked()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_the_result_of_a_cancelled_write_is_still_stored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test what the camera did is recorded, even if nobody waits for it."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    camera = SlowCamera(
        result=ImageWriteResult(True, 200, "ok", {"HLC/enabled": "false"})
    )
    mock_image_settings.set_image_setting = camera.set_image_setting

    write = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "10"))
    await camera.wait_until_started()
    write.cancel()
    camera.release.set()
    await hass.async_block_till_done()

    assert coordinator.data[BRIGHTNESS] == "10"
    assert coordinator.data["HLC/enabled"] == "false"


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_rejected_password_is_dealt_with_even_if_the_caller_was_stopped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test nothing else is sent, and new credentials are asked for."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    camera = SlowCamera(ISAPIAuthError("Unauthorized", 401))
    mock_image_settings.set_image_setting = camera.set_image_setting

    write = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "10"))
    await camera.wait_until_started()
    write.cancel()
    camera.release.set()
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.image_credentials_rejected
    assert not coordinator.last_update_success
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_a_request_of_an_earlier_setup_does_not_reject_the_new_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a refusal that comes after another setup began is not held against it."""
    await setup_integration(hass, mock_config_entry)
    old = mock_config_entry.runtime_data
    coordinator = old.image_coordinators[0]
    camera = SlowCamera(ISAPIAuthError("Unauthorized", 401))
    mock_image_settings.set_image_setting = camera.set_image_setting
    write = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "10"))
    await camera.wait_until_started()

    new = copy.copy(old)
    mock_config_entry.runtime_data = new
    camera.release.set()
    with pytest.raises(HomeAssistantError):
        await write
    await hass.async_block_till_done()

    assert not new.image_credentials_rejected
    mock_hikcamera.return_value.disconnect.assert_not_called()
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_image_settings")
async def test_the_stream_waits_for_the_request_that_is_running(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the result of a request does not undo the rejection of the password."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    camera = SlowCamera()
    mock_image_settings.set_image_setting = camera.set_image_setting
    write = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "10"))
    await camera.wait_until_started()

    stream = mock_hikcamera.return_value
    stream.stream_auth_failed = True
    callback = next(
        call.args[0]
        for call in stream.add_update_callback.call_args_list
        if call.args[1] == STREAM_CREDENTIALS_ID
    )
    await hass.async_add_executor_job(callback, STREAM_CREDENTIALS_ID)
    await asyncio.sleep(0.05)

    # The stream is stopped at once, the coordinators when the request has ended.
    stream.disconnect.assert_called_once()
    assert coordinator.last_update_success
    assert not hass.config_entries.flow.async_progress()

    camera.release.set()
    await write
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert len(hass.config_entries.flow.async_progress()) == 1


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_request_that_was_queued_does_not_run_once_the_entry_unloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a request waiting for the client does not use it after the unload."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    request = MagicMock()

    await coordinator.lock.acquire()
    queued = hass.async_create_task(coordinator.async_request(request))
    await asyncio.sleep(0)
    # What unloading does before it waits for the client.
    coordinator.closed = True
    coordinator.lock.release()

    with pytest.raises(ISAPIConnectionError):
        await queued
    request.assert_not_called()
    assert not coordinator.lock.locked()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_unloading_closes_the_coordinators_to_new_requests(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the coordinators refuse requests from the start of the unload."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    assert not coordinator.closed

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert coordinator.closed
    with pytest.raises(ISAPIConnectionError):
        await coordinator.async_request(MagicMock())


class SlowRead:
    """A read of the values that takes as long as the test wants."""

    def __init__(self) -> None:
        """Initialize the read."""
        self.started = threading.Event()
        self.release = threading.Event()

    def get_image_values(self) -> dict[str, str]:
        """Read the values, when the test lets it end."""
        self.started.set()
        assert self.release.wait(5)
        return {BRIGHTNESS: "99"}


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_poll_that_ends_after_the_credentials_were_rejected_is_dropped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the result of a poll does not make the entities available again."""
    await setup_integration(hass, mock_config_entry)
    entry = mock_config_entry
    coordinator = entry.runtime_data.image_coordinators[0]
    read = SlowRead()
    mock_image_settings.get_image_values = read.get_image_values

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    async with asyncio.timeout(5):
        while not read.started.is_set():
            await asyncio.sleep(0)
    # The event stream is refused the password while the poll is running.
    rejection = hass.async_create_task(async_reject_credentials(hass, entry))
    await asyncio.sleep(0)
    read.release.set()
    await rejection
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert coordinator.data.get(BRIGHTNESS) != "99"


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_cancelled_discovery_keeps_the_client_until_it_ends(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a request of the setup, like the others, is not left on a free client."""
    await setup_integration(hass, mock_config_entry)
    lock = asyncio.Lock()
    started = threading.Event()
    release = threading.Event()

    def request() -> str:
        started.set()
        assert release.wait(5)
        return "done"

    discovery = hass.async_create_task(
        async_run_alone(hass, mock_config_entry, lock, request)
    )
    async with asyncio.timeout(5):
        while not started.is_set():
            await asyncio.sleep(0)
    discovery.cancel()
    with pytest.raises(asyncio.CancelledError):
        await discovery

    assert lock.locked()
    release.set()
    await hass.async_block_till_done()
    assert not lock.locked()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_unloading_waits_for_the_request_that_is_running(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the unload does not return while a request is using the client."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]
    camera = SlowCamera()
    mock_image_settings.set_image_setting = camera.set_image_setting
    write = hass.async_create_task(coordinator.async_set_setting(BRIGHTNESS, "10"))
    await camera.wait_until_started()

    unload = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    await asyncio.sleep(0.05)
    assert not unload.done()

    camera.release.set()
    await unload
    await write


@pytest.mark.parametrize(
    ("state", "current"),
    [
        (ConfigEntryState.LOADED, True),
        (ConfigEntryState.SETUP_IN_PROGRESS, True),
        (ConfigEntryState.FAILED_UNLOAD, True),
        (ConfigEntryState.NOT_LOADED, False),
        (ConfigEntryState.UNLOAD_IN_PROGRESS, False),
    ],
)
async def test_entry_is_current_while_its_setup_is_still_running(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    state: ConfigEntryState,
    current: bool,
) -> None:
    """Test a setup whose unload failed still counts, as it keeps running."""
    await setup_integration(hass, mock_config_entry)
    data = mock_config_entry.runtime_data

    mock_config_entry.mock_state(hass, state)

    assert entry_is_current(mock_config_entry, data) is current
    assert entry_is_current(mock_config_entry, object()) is False
