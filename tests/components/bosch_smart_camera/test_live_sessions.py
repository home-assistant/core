"""Test the local live stream of the Bosch Smart Camera integration."""

import asyncio
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
    CameraModel,
)
from bosch_shc_camera_client.live import LiveConnection
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bosch_smart_camera.const import DOMAIN
from homeassistant.components.bosch_smart_camera.coordinator import SCAN_INTERVAL
from homeassistant.components.camera import DATA_COMPONENT, async_get_stream_source
from homeassistant.components.camera.webrtc import (
    CameraWebRTCProvider,
    async_register_webrtc_provider,
)
from homeassistant.components.stream import Stream
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import CAMERA_ID, CAMERAS

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "camera.garden"
OTHER_ID = "22222222-2222-2222-2222-222222222222"
OTHER = Camera(OTHER_ID, "Hall", "HOME_Eyes_Indoor", CameraModel.EYES_INDOOR_II, None)
RENEWAL = timedelta(seconds=3300)
EXPIRY = timedelta(seconds=300)
CAMERA_MODULE = "homeassistant.components.bosch_smart_camera.camera"
MODULE = "homeassistant.components.bosch_smart_camera.live_sessions"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry whose token outlives the renewals."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="fake-account-sub",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "fake-access-token",
                "refresh_token": "fake-refresh-token",
                "expires_at": dt_util.utcnow().timestamp() + 86400,
            },
        },
    )


@dataclass
class LiveMocks:
    """The mocked library calls of a live session."""

    open: AsyncMock
    start_proxy: AsyncMock
    stop_proxy: AsyncMock
    stop_all: AsyncMock
    pre_warm: AsyncMock
    proxy_died: dict[str, Callable[[], None]] = field(default_factory=dict)


@pytest.fixture
def mock_live() -> Generator[LiveMocks]:
    """Mock the library calls that talk to the camera."""
    opened = 0
    ports = 0

    async def open_connection(
        session: object, token: str, camera_id: str
    ) -> LiveConnection:
        nonlocal opened
        opened += 1
        return LiveConnection(
            connection_type="LOCAL",
            host="10.0.0.5",
            port=443,
            username=f"user{opened}",
            password=f"pass{opened}",
            snapshot_url="https://10.0.0.5/snap.jpg",
            max_session_seconds=3600,
            buffering_ms=500,
        )

    async def start_proxy(*args: object, **kwargs: Callable[[], None]) -> int:
        nonlocal ports
        ports += 1
        mocks.proxy_died[args[1]] = kwargs["on_proxy_died"]
        return 20000 + ports

    with (
        patch(f"{MODULE}.open_local_live_connection", side_effect=open_connection) as o,
        patch(f"{MODULE}.start_tls_proxy", side_effect=start_proxy) as start,
        patch(f"{MODULE}.stop_tls_proxy") as stop,
        patch(f"{MODULE}.stop_all_proxies") as stop_all,
        patch(f"{MODULE}.pre_warm_rtsp", return_value=True) as pre_warm,
    ):
        mocks = LiveMocks(o, start, stop, stop_all, pre_warm)
        yield mocks


async def _hang(*args: object, **kwargs: object) -> bool:
    await asyncio.sleep(3600)
    return True


async def _fire(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    delay: timedelta = RENEWAL,
) -> None:
    freezer.tick(delay + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _entity(hass: HomeAssistant, entity_id: str = ENTITY_ID):
    return hass.data[DATA_COMPONENT].get_entity(entity_id)


async def _watch(
    hass: HomeAssistant, *, viewer: bool = True, preload: bool = False
) -> Stream:
    """Create the real stream of the camera, optionally with a viewer."""
    assert await async_setup_component(hass, "stream", {})
    stream = await _entity(hass).async_create_stream()
    if viewer:
        stream.add_provider("hls")
    stream.dynamic_stream_settings.preload_stream = preload
    return stream


async def test_stream_source(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test the stream source is the local proxy and a session opens once."""
    await setup_integration(hass, mock_config_entry)

    url = await async_get_stream_source(hass, ENTITY_ID)

    assert (
        url
        == "rtsp://user1:pass1@127.0.0.1:20001/rtsp_tunnel?inst=1&enableaudio=1&fmtp=1&maxSessionDuration=3600"
    )
    assert await async_get_stream_source(hass, ENTITY_ID) == url
    assert _entity(hass).stream_options == {"rtsp_transport": "tcp"}
    mock_live.open.assert_awaited_once()
    mock_live.start_proxy.assert_awaited_once()
    mock_live.pre_warm.assert_awaited_once_with(
        20001, "user1", "pass1", "10.0.0.5", max_session_duration=3600
    )


async def test_concurrent_requests_open_one_session(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test simultaneous stream requests share one session."""
    await setup_integration(hass, mock_config_entry)

    urls = await asyncio.gather(
        *(async_get_stream_source(hass, ENTITY_ID) for _ in range(3))
    )

    assert len(set(urls)) == 1
    mock_live.open.assert_awaited_once()
    mock_live.start_proxy.assert_awaited_once()


async def test_slow_open_survives_a_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test a request that gives up does not abort the open for the next one."""
    release = asyncio.Event()

    async def slow(*args: object, **kwargs: object) -> bool:
        await release.wait()
        return True

    mock_live.pre_warm.side_effect = slow
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await async_get_stream_source(hass, ENTITY_ID)
    release.set()

    assert await async_get_stream_source(hass, ENTITY_ID)
    mock_live.open.assert_awaited_once()


async def test_idle_session_is_not_renewed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unused session is kept until the camera ends it, then dropped."""
    await setup_integration(hass, mock_config_entry)
    first = await async_get_stream_source(hass, ENTITY_ID)

    await _fire(hass, freezer)

    mock_live.open.assert_awaited_once()
    mock_live.stop_proxy.assert_not_called()
    assert await async_get_stream_source(hass, ENTITY_ID) == first

    await _fire(hass, freezer, EXPIRY)

    mock_live.stop_proxy.assert_awaited_once()
    assert await async_get_stream_source(hass, ENTITY_ID) != first
    assert mock_live.open.await_count == 2


async def test_expired_session_releases_the_stream(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stream without viewers is stopped and forgotten at expiry."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    stream = await _watch(hass, viewer=False)

    await _fire(hass, freezer)
    assert _entity(hass).stream is stream
    await _fire(hass, freezer, EXPIRY)

    assert _entity(hass).stream is None
    assert stream.access_token is None
    mock_live.open.assert_awaited_once()


async def test_viewer_in_the_last_minutes_gets_a_renewed_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a viewer who starts after the idle check is not cut off at expiry."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    stream = await _watch(hass, viewer=False)
    await _fire(hass, freezer)
    mock_live.open.assert_awaited_once()

    stream.add_provider("hls")
    await _fire(hass, freezer, EXPIRY)

    assert mock_live.open.await_count == 2
    assert "user2" in stream.source
    assert _entity(hass).stream is stream
    assert stream.outputs()


async def test_expiry_of_a_replaced_session_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the expiry of a session that is already gone does nothing."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    live = mock_config_entry.runtime_data.live_sessions
    session = live._sessions[CAMERA_ID]
    await live.async_close(CAMERA_ID)

    await live._async_expire(CAMERA_ID, session)

    mock_live.stop_proxy.assert_awaited_once()


async def test_renewal_while_streaming(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a used session gets a new proxy and the stream a new source."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    stream = await _watch(hass)

    await _fire(hass, freezer)

    assert mock_live.open.await_count == 2
    assert mock_live.start_proxy.await_count == 2
    assert stream.source == (
        "rtsp://user2:pass2@127.0.0.1:20002/rtsp_tunnel?inst=1&enableaudio=1&fmtp=1&maxSessionDuration=3600"
    )

    await _fire(hass, freezer)
    assert mock_live.open.await_count == 3


async def test_renewal_of_a_preloaded_stream(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a preloaded stream counts as in use even without a viewer."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    stream = await _watch(hass, viewer=False, preload=True)

    await _fire(hass, freezer)

    assert mock_live.open.await_count == 2
    assert "user2" in stream.source


async def test_renewal_without_entity_stream(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a renewal that finds the stream gone leaves the entity alone."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    live = mock_config_entry.runtime_data.live_sessions
    live._sessions[CAMERA_ID].is_streaming = lambda: True

    await _fire(hass, freezer)

    assert mock_live.open.await_count == 2


@pytest.mark.parametrize("error", [None, TimeoutError])
async def test_renewal_failure_ends_the_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    error: type[Exception] | None,
) -> None:
    """Test any failed renewal drops the session and the stream."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    await _watch(hass)
    if error:
        patcher = patch.object(
            OAuth2Session, "async_ensure_token_valid", side_effect=error
        )
    else:
        mock_live.pre_warm.return_value = False
        patcher = patch.object(OAuth2Session, "async_ensure_token_valid")

    with patcher:
        await _fire(hass, freezer)

    assert "Could not renew the live session" in caplog.text
    assert _entity(hass).stream is None
    mock_live.pre_warm.return_value = True
    assert await async_get_stream_source(hass, ENTITY_ID)


async def test_stale_renewal_is_ignored(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test a renewal of a session that is already gone does nothing."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    live = mock_config_entry.runtime_data.live_sessions
    session = live._sessions[CAMERA_ID]
    await live.async_close(CAMERA_ID)

    await live._async_renew(CAMERA_ID, session)

    mock_live.open.assert_awaited_once()


@pytest.mark.parametrize(
    "error",
    [BoschCameraConnectionError, BoschCameraInvalidResponseError],
)
async def test_open_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    error: type[Exception],
) -> None:
    """Test library errors surface as a translated error and can be retried."""
    await setup_integration(hass, mock_config_entry)
    real = mock_live.open.side_effect
    mock_live.open.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_get_stream_source(hass, ENTITY_ID)
    assert exc_info.value.translation_key == "stream_failed"
    assert exc_info.value.translation_domain == DOMAIN

    mock_live.open.side_effect = real
    assert await async_get_stream_source(hass, ENTITY_ID)


async def test_auth_error_starts_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test a rejected token asks the user to sign in again."""
    await setup_integration(hass, mock_config_entry)
    mock_live.open.side_effect = BoschCameraAuthError

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_get_stream_source(hass, ENTITY_ID)

    assert exc_info.value.translation_key == "auth_failed"
    mock_live.start_proxy.assert_not_called()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert all(flow["context"]["source"] == "reauth" for flow in flows)


async def test_failed_pre_warm(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test a camera that does not answer leaves no proxy behind."""
    await setup_integration(hass, mock_config_entry)
    mock_live.pre_warm.return_value = False

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_get_stream_source(hass, ENTITY_ID)

    assert exc_info.value.translation_key == "stream_failed"
    mock_live.stop_proxy.assert_awaited_once()
    mock_live.pre_warm.return_value = True
    assert await async_get_stream_source(hass, ENTITY_ID)


async def test_cameras_are_isolated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test one failing camera does not affect another."""
    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    await setup_integration(hass, mock_config_entry)
    real = mock_live.open.side_effect

    async def fail_for_other(session: object, token: str, camera_id: str):
        if camera_id == OTHER_ID:
            raise BoschCameraConnectionError
        return await real(session, token, camera_id)

    mock_live.open.side_effect = fail_for_other

    with pytest.raises(HomeAssistantError):
        await async_get_stream_source(hass, "camera.hall")
    assert await async_get_stream_source(hass, ENTITY_ID)

    mock_live.open.side_effect = real
    other_url = await async_get_stream_source(hass, "camera.hall")
    mock_live.proxy_died[OTHER_ID]()
    await hass.async_block_till_done()
    assert CAMERA_ID in mock_config_entry.runtime_data.live_sessions.camera_ids
    assert OTHER_ID not in mock_config_entry.runtime_data.live_sessions.camera_ids
    assert await async_get_stream_source(hass, "camera.hall") != other_url


async def test_proxy_death_drops_session_and_stream(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test a dead proxy makes the next request open a new session."""
    await setup_integration(hass, mock_config_entry)
    first = await async_get_stream_source(hass, ENTITY_ID)
    await _watch(hass)

    mock_live.proxy_died[CAMERA_ID]()
    await hass.async_block_till_done()

    assert _entity(hass).stream is None
    assert await async_get_stream_source(hass, ENTITY_ID) != first
    assert mock_live.open.await_count == 2


async def test_proxy_death_moves_a_preloaded_stream(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test a preloaded stream keeps its worker and gets the new session."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    stream = await _watch(hass, viewer=False, preload=True)

    mock_live.proxy_died[CAMERA_ID]()
    await hass.async_block_till_done()

    assert _entity(hass).stream is stream
    assert "user2" in stream.source


async def test_preloaded_stream_recovers_after_a_failed_reopen(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test the reopen of a preloaded stream is retried until it works."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    stream = await _watch(hass, viewer=False, preload=True)
    source = stream.source
    real = mock_live.open.side_effect
    mock_live.open.side_effect = BoschCameraConnectionError

    with patch(f"{CAMERA_MODULE}.REOPEN_INTERVAL", 0.01):
        mock_live.proxy_died[CAMERA_ID]()
        await asyncio.sleep(0.05)
        assert stream.source == source
        mock_live.open.side_effect = real
        async with asyncio.timeout(5):
            while stream.source == source:
                await asyncio.sleep(0.01)

    assert _entity(hass).stream is stream
    assert "user" in stream.source


async def test_unload_stops_the_reopen_retry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test unloading ends a reopen that keeps failing."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    entity = _entity(hass)
    await _watch(hass, viewer=False, preload=True)
    mock_live.open.side_effect = BoschCameraConnectionError
    mock_live.proxy_died[CAMERA_ID]()
    await asyncio.sleep(0)
    task = entity._reopen_task
    assert task

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert task.cancelled()


@pytest.mark.parametrize("preload", [False, True])
async def test_unload_stops_the_stream_worker(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    preload: bool,
) -> None:
    """Test unloading ends the worker of a started stream, preloaded or not."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    entity = _entity(hass)
    stream = await _watch(hass, preload=preload)
    await stream.start()
    assert stream._thread.is_alive()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert stream._thread is None
    assert entity.stream is None


async def test_removing_the_entity_closes_its_session_and_keeps_the_settings(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test a removed camera releases its session without touching cached settings."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    entity = _entity(hass)
    stream = await _watch(hass, preload=True)
    settings = stream.dynamic_stream_settings

    await entity.async_will_remove_from_hass()

    assert CAMERA_ID not in entity.coordinator.live_sessions.camera_ids
    assert settings.preload_stream is True
    assert entity.stream is None


async def test_close_all_releases_open_sessions(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test closing everything drops the sessions that still exist."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    await hass.async_block_till_done()
    sessions = mock_config_entry.runtime_data.live_sessions
    assert sessions.camera_ids

    await sessions.async_close_all()

    assert not sessions.camera_ids


async def test_late_proxy_death_of_an_old_proxy_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the report of a replaced proxy does not drop the new session."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    old_callback = mock_live.proxy_died[CAMERA_ID]
    await _watch(hass)
    await _fire(hass, freezer)
    renewed = await async_get_stream_source(hass, ENTITY_ID)

    old_callback()

    assert await async_get_stream_source(hass, ENTITY_ID) == renewed
    assert mock_live.open.await_count == 2


async def test_proxy_start_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test a proxy that cannot listen surfaces a translated error."""
    mock_live.start_proxy.side_effect = OSError
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_get_stream_source(hass, ENTITY_ID)

    assert exc_info.value.translation_key == "stream_failed"


async def test_unload_while_renewing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading ends a renewal in flight instead of letting it revive."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    await _watch(hass)
    mock_live.pre_warm.side_effect = _hang
    freezer.tick(RENEWAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    live = mock_config_entry.runtime_data.live_sessions
    assert live._renewals

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await _fire(hass, freezer, EXPIRY)

    assert not live._renewals
    assert not live._sessions
    mock_live.stop_all.assert_awaited_once()
    assert mock_live.open.await_count == 2


async def test_removed_camera_ends_a_renewal_in_flight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing a camera cancels its renewal in flight."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    await _watch(hass)
    mock_live.pre_warm.side_effect = _hang
    freezer.tick(RENEWAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    mock_list_cameras.return_value = [OTHER]

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not mock_config_entry.runtime_data.live_sessions.camera_ids


async def test_unload_closes_sessions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading stops the proxies and the pending renewal."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await _fire(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_live.stop_all.assert_awaited_once()
    mock_live.open.assert_awaited_once()


async def test_unload_while_opening(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_live: LiveMocks
) -> None:
    """Test unloading cancels a session that is still being opened."""
    mock_live.pre_warm.side_effect = _hang
    await setup_integration(hass, mock_config_entry)
    request = hass.async_create_task(async_get_stream_source(hass, ENTITY_ID))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert request.done()
    mock_live.stop_all.assert_awaited_once()


async def test_removed_camera_closes_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a camera that leaves the account loses its session."""
    await setup_integration(hass, mock_config_entry)
    await async_get_stream_source(hass, ENTITY_ID)
    mock_list_cameras.return_value = [OTHER]

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_live.stop_proxy.assert_awaited_once()
    assert not mock_config_entry.runtime_data.live_sessions.camera_ids


async def test_removed_camera_cancels_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_live: LiveMocks,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a camera that leaves the account stops being opened."""
    mock_live.pre_warm.side_effect = _hang
    await setup_integration(hass, mock_config_entry)
    request = hass.async_create_task(async_get_stream_source(hass, ENTITY_ID))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    mock_list_cameras.return_value = [OTHER]

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert request.done()
    assert not mock_config_entry.runtime_data.live_sessions.camera_ids


async def test_provider_discovery_does_not_open_sessions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_live: LiveMocks,
) -> None:
    """Test a registered WebRTC provider does not open a live session at setup."""
    provider = MagicMock(spec=CameraWebRTCProvider)
    provider.domain = "test"
    provider.async_is_supported.return_value = True
    assert await async_setup_component(hass, "camera", {})
    async_register_webrtc_provider(hass, provider)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID)
    mock_live.open.assert_not_called()
    provider.async_is_supported.assert_not_called()
