"""Test the UniFi Network connection manager."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterator
from contextlib import contextmanager
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import aiounifi
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.unifi.const import DOMAIN
from homeassistant.components.unifi.coordinator import (
    IDLE_POLL_INTERVAL,
    UPDATE_TIMEOUT,
    UnifiDataUpdateCoordinator,
)
from homeassistant.components.unifi.hub import UnifiHub
from homeassistant.components.unifi.hub.connection import (
    CONNECTION_STABLE_PERIOD,
    LOGIN_REJECTIONS_BEFORE_REAUTH,
    MAX_RATE_LIMIT_PAUSE,
    RATE_LIMIT_PAUSE,
    REAUTH_RETRY_INTERVAL,
    RECOVERY_TIMEOUT,
    REQUEST_TIMEOUT,
    RETRY_DELAYS,
    RETRY_JITTER,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .conftest import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SITE,
    FIRST_RETRY_DELAY,
    MAX_RETRY_DELAY,
    ConfigEntryFactoryType,
    WebsocketStateManager,
    invalid_json,
    retry_window,
)

JITTER = "homeassistant.components.unifi.hub.connection.random.uniform"
# A client entity is available exactly while the session is
CLIENT_ENTITY = "device_tracker.client_1"
LOST = f"Connection to UniFi Network at {DEFAULT_HOST} lost"

CLIENT_MAC = "00:00:00:00:00:01"


@pytest.fixture(name="client_payload")
def fixture_client_payload(
    entity_registry: er.EntityRegistry, config_entry: MockConfigEntry
) -> list[dict[str, Any]]:
    """Provide one client whose entity follows the session availability."""
    # Enabling the tracker during setup would reload the entry later
    entity_registry.async_get_or_create(
        TRACKER_DOMAIN,
        DOMAIN,
        f"{DEFAULT_SITE}-{CLIENT_MAC}",
        suggested_object_id="client_1",
        config_entry=config_entry,
    )
    return [
        {
            "ap_mac": "00:00:00:00:02:01",
            "essid": "ssid",
            "hostname": "client_1",
            "ip": "10.0.0.1",
            "is_wired": False,
            "last_seen": 1562600145,
            "mac": CLIENT_MAC,
        }
    ]


def _available(hass: HomeAssistant) -> bool:
    """Return if the entities of the session are available."""
    return hass.states.get(CLIENT_ENTITY).state != STATE_UNAVAILABLE


def _fire(hass: HomeAssistant, seconds: float) -> None:
    """Fire timers due within the given number of seconds, without waiting."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))


async def _advance(hass: HomeAssistant, seconds: float) -> None:
    """Fire timers due within the given number of seconds and wait for them."""
    _fire(hass, seconds)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _wait(event: asyncio.Event) -> None:
    """Wait for an event, failing instead of hanging when it never comes."""
    async with asyncio.timeout(5):
        await event.wait()


def _availability_reached(
    hass: HomeAssistant, entry: MockConfigEntry, available: bool
) -> asyncio.Event:
    """Return an event set once the entities reach the given availability."""
    reached = asyncio.Event()

    @callback
    def _changed(event: Event[EventStateChangedData]) -> None:
        state = event.data["new_state"]
        if state is not None and (state.state != STATE_UNAVAILABLE) is available:
            reached.set()

    entry.async_on_unload(async_track_state_change_event(hass, CLIENT_ENTITY, _changed))
    return reached


def _logged(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    """Return the records the integration logged at or above the given level."""
    return [
        record
        for record in caplog.records
        if record.name.startswith("homeassistant.components.unifi")
        and record.levelno >= level
    ]


def _reauth_requested(hass: HomeAssistant, entry: MockConfigEntry) -> bool:
    """Return if the entry asks the user to log in again."""
    return bool(list(entry.async_get_active_flows(hass, {SOURCE_REAUTH})))


@contextmanager
def _expired_session(
    hub: UnifiHub, login: AsyncMock | None = None, probe: AsyncMock | None = None
) -> Iterator[AsyncMock]:
    """Let the readiness probe ask for a login until one worked.

    Once logged in, the probe answers like the given mock.
    """
    login = login or AsyncMock()
    probe = probe or AsyncMock()
    logged_in = False

    async def _login() -> None:
        nonlocal logged_in
        await login()
        logged_in = True

    async def _probe() -> None:
        if not logged_in:
            raise aiounifi.LoginRequired
        await probe()

    with (
        patch.object(hub.api, "login", side_effect=_login),
        patch.object(hub.api.system_information, "update", side_effect=_probe),
    ):
        yield login


@contextmanager
def _recovery_loses_session(
    hub: UnifiHub, login: AsyncMock | None = None
) -> Iterator[tuple[AsyncMock, AsyncMock]]:
    """Log in fine, then lose the session again while the clients are refetched."""
    # The readiness probe passes, the checks after the failed refetch do not
    probe = AsyncMock(side_effect=[None, *[aiounifi.LoginRequired()] * 10])
    with (
        _expired_session(hub, login, probe) as login_mock,
        patch.object(hub.api.clients, "update", side_effect=aiounifi.RequestError),
    ):
        yield login_mock, probe


def _fail_first_call(
    exception: Exception,
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Return a side effect that raises once, then answers."""
    calls = 0

    async def side_effect(*args: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise exception

    return side_effect


def _hang_first_call(
    started: asyncio.Event,
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Return a side effect that never answers once, then fails fast."""
    calls = 0

    async def side_effect(*args: object) -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise aiounifi.RequestError
        started.set()
        await asyncio.Event().wait()

    return side_effect


async def _unload(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def _fire_stop(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


PARAMETRIZE_STOP = pytest.mark.parametrize(
    "stop",
    [
        pytest.param(_unload, id="unload"),
        pytest.param(_fire_stop, id="homeassistant_stop"),
    ],
)


def _login_requests(aioclient_mock: AiohttpClientMocker) -> int:
    """Return how often the client logged in."""
    return sum(
        1
        for method, url, *_ in aioclient_mock.mock_calls
        if method.lower() == "post" and url.path == "/api/login"
    )


@pytest.fixture(autouse=True)
def fixture_retry_jitter() -> Iterator[None]:
    """Retry in the middle of the jitter, tests of its bounds patch it again."""
    with patch(JITTER, return_value=1.0):
        yield


@pytest.fixture(name="hub")
def fixture_hub(config_entry_setup: MockConfigEntry) -> UnifiHub:
    """Return the hub of the set up entry."""
    return config_entry_setup.runtime_data


@pytest.fixture(name="polled_coordinator")
def fixture_polled_coordinator(hub: UnifiHub) -> UnifiDataUpdateCoordinator:
    """Return a coordinator that polls its handler."""
    return hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )


async def test_connection_state_signalling(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Verify connection state signalling and connection state are working."""
    assert _available(hass)

    await mock_websocket_state.disconnect()
    assert not _available(hass)

    # The session outlived the outage, so no login is needed
    logins = _login_requests(aioclient_mock)
    await mock_websocket_state.reconnect()
    assert _login_requests(aioclient_mock) == logins
    assert _available(hass)


async def test_unexpected_login_error_logs_one_traceback_per_outage(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A login that keeps failing unexpectedly does not flood the log."""

    def errors() -> int:
        return len(_logged(caplog, logging.ERROR))

    with _expired_session(hub, AsyncMock(side_effect=KeyError)) as login:
        await mock_websocket_state.disconnect()
        for _ in range(3):
            await _advance(hass, MAX_RETRY_DELAY)
    assert login.call_count == 3
    assert errors() == 1

    mock_websocket_state.clear()
    with _expired_session(hub):
        await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass)

    # A new outage logs the traceback again
    with _expired_session(hub, AsyncMock(side_effect=KeyError)):
        await mock_websocket_state.disconnect()
        await _advance(hass, MAX_RETRY_DELAY)
    assert errors() == 2


async def test_reconnect_backoff_grows_caps_and_resets(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Retry later after each failed login and start over once stable."""
    logins: list[int] = []

    with _expired_session(hub, AsyncMock(side_effect=aiounifi.RequestError)) as login:
        await mock_websocket_state.disconnect()
        for attempt in range(4):
            earliest, latest = retry_window(attempt)
            await _advance(hass, earliest - 1)
            logins.append(login.call_count)
            await _advance(hass, latest)
            logins.append(login.call_count)
    # 15 s, 30 s, then capped at 60 s, each spread by jitter
    assert logins == [0, 1, 1, 2, 2, 3, 3, 4]

    mock_websocket_state.clear()
    with _expired_session(hub):
        await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass)

    # Only a connection that stayed up starts the backoff over
    await _advance(hass, CONNECTION_STABLE_PERIOD)
    with _expired_session(hub, AsyncMock(side_effect=aiounifi.RequestError)) as login:
        await mock_websocket_state.disconnect()
        await _advance(hass, FIRST_RETRY_DELAY)
    login.assert_called_once()


async def test_concurrent_failures_check_session_and_reconnect_once(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Endpoints and the websocket failing together share one check and retry."""
    probe_started = asyncio.Event()
    probe_release = asyncio.Event()

    async def slow_probe() -> None:
        probe_started.set()
        await probe_release.wait()
        raise aiounifi.RequestError

    with (
        patch.object(
            hub.api.object_oriented_network_configs,
            "update",
            side_effect=aiounifi.RequestError,
        ),
        patch.object(
            hub.api.traffic_rules, "update", side_effect=aiounifi.RequestError
        ),
        patch.object(
            hub.api.system_information, "update", side_effect=slow_probe
        ) as probe,
        patch.object(hub.api, "login", side_effect=aiounifi.RequestError) as login,
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await _wait(probe_started)
        await hass.async_block_till_done()
        # The websocket drops too while the session check runs
        mock_websocket_state.set()
        await hass.async_block_till_done()
        probe_release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        probe.assert_called_once()

        await _advance(hass, FIRST_RETRY_DELAY)

    # One retry, which does not log in while the application is unreachable
    assert probe.call_count == 2
    login.assert_not_called()
    assert caplog.text.count(LOST) == 1


@PARAMETRIZE_STOP
async def test_pending_retry_is_dropped_on_stop(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    stop: Callable[[HomeAssistant, MockConfigEntry], Awaitable[None]],
) -> None:
    """A retry scheduled before unload or shutdown never logs in."""
    hub = config_entry_setup.runtime_data

    with _expired_session(hub) as login:
        await mock_websocket_state.disconnect()
        await stop(hass, config_entry_setup)
        await _advance(hass, MAX_RETRY_DELAY)

    login.assert_not_called()


@PARAMETRIZE_STOP
async def test_login_in_flight_at_stop_does_not_retry(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    stop: Callable[[HomeAssistant, MockConfigEntry], Awaitable[None]],
) -> None:
    """Stopping abandons a hanging login and schedules no further attempt."""
    hub = config_entry_setup.runtime_data
    login_started = asyncio.Event()
    login_cancelled = asyncio.Event()

    async def hang() -> None:
        login_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            login_cancelled.set()
            raise

    with _expired_session(hub, AsyncMock(side_effect=hang)) as login:
        await mock_websocket_state.disconnect()
        _fire(hass, FIRST_RETRY_DELAY)
        await _wait(login_started)

        await stop(hass, config_entry_setup)
        assert login_cancelled.is_set()
        await _advance(hass, MAX_RETRY_DELAY)

    login.assert_called_once()


@pytest.mark.parametrize("expected_lingering_timers", [False])
async def test_failed_setup_does_not_retry(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Nothing keeps polling or logging in after setup failed."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        side_effect=RuntimeError,
    ):
        config_entry = await config_entry_factory()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    with _expired_session(config_entry.runtime_data) as login:
        await _advance(hass, (IDLE_POLL_INTERVAL * 2).total_seconds())

    login.assert_not_called()


@pytest.mark.parametrize(
    ("exception", "logins"),
    [
        pytest.param(aiounifi.TwoFaTokenRequired, 1, id="two_factor"),
        # A booting console can reject a login for a moment
        pytest.param(aiounifi.Unauthorized, 3, id="unauthorized"),
        pytest.param(aiounifi.Forbidden, 3, id="forbidden"),
        pytest.param(aiounifi.NoPermission, 3, id="no_permission"),
    ],
)
async def test_rejected_login_starts_reauth_and_retries_slowly(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
    logins: int,
) -> None:
    """Ask the user to fix the login, and recover if it works again meanwhile."""
    hub = config_entry_setup.runtime_data
    login = AsyncMock(side_effect=exception)

    with _expired_session(hub, login):
        await mock_websocket_state.disconnect()
        for _ in range(logins + 1):
            await _advance(hass, MAX_RETRY_DELAY)
        assert login.call_count == logins
        assert _reauth_requested(hass, config_entry_setup)

        await _advance(hass, REAUTH_RETRY_INTERVAL)
        assert login.call_count == logins + 1

        # An unexpected error keeps the slow pace
        login.side_effect = KeyError
        await _advance(hass, REAUTH_RETRY_INTERVAL)
        await _advance(hass, MAX_RETRY_DELAY)
        assert login.call_count == logins + 2
        assert not _available(hass)

        login.side_effect = None
        mock_websocket_state.clear()
        await _advance(hass, REAUTH_RETRY_INTERVAL)

    assert _available(hass)
    assert not _reauth_requested(hass, config_entry_setup)


@pytest.mark.parametrize(
    "logins",
    [
        # UniFi OS answers a login with 401 while its login service is down
        pytest.param([*[aiounifi.LoginRequired()] * 5, None], id="login_service_down"),
        # A console that rejects logins while booting recovers on its own
        pytest.param(
            [aiounifi.Unauthorized(), aiounifi.Unauthorized(), None],
            id="briefly_rejected",
        ),
        pytest.param(
            [
                aiounifi.Forbidden(),
                TimeoutError(),
                aiounifi.Forbidden(),
                aiounifi.Forbidden(),
                None,
            ],
            id="rejections_not_in_a_row",
        ),
        pytest.param([TimeoutError(), None], id="timeout"),
        pytest.param([aiounifi.BadGateway(), None], id="bad_gateway"),
        pytest.param([aiounifi.ServiceUnavailable(), None], id="service_unavailable"),
        pytest.param([aiounifi.AiounifiException(), None], id="unknown_error"),
    ],
)
async def test_login_failures_that_do_not_start_reauth(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    logins: list[Exception | None],
) -> None:
    """Keep backing off when the login fails for other reasons than credentials."""
    hub = config_entry_setup.runtime_data

    with _expired_session(hub, AsyncMock(side_effect=logins)):
        await mock_websocket_state.disconnect()
        mock_websocket_state.clear()
        for _ in logins:
            await _advance(hass, MAX_RETRY_DELAY)

    assert _available(hass)
    assert not _reauth_requested(hass, config_entry_setup)
    assert not _logged(caplog, logging.ERROR)


@pytest.mark.parametrize(
    ("exception", "ready"),
    [
        pytest.param(aiounifi.ServiceUnavailable, False, id="starting"),
        pytest.param(aiounifi.RequestError, False, id="unreachable"),
        pytest.param(TimeoutError, False, id="timeout"),
        pytest.param(aiounifi.LoginRequired, False, id="session_expired"),
        pytest.param(invalid_json(), False, id="invalid_json"),
        pytest.param(KeyError, False, id="unexpected_error"),
        # The fresh session may not read the application
        pytest.param(aiounifi.Unauthorized, False, id="unauthorized"),
        pytest.param(aiounifi.Forbidden, False, id="forbidden"),
        pytest.param(aiounifi.NoPermission, False, id="no_permission"),
        # The application answers the fresh session
        pytest.param(aiounifi.ResponseError, True, id="response_error"),
    ],
)
async def test_readiness_probe_after_login(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
    ready: bool,
) -> None:
    """Restore the session only once the Network application answers."""
    hub = config_entry_setup.runtime_data

    with _expired_session(hub, probe=AsyncMock(side_effect=exception)):
        await mock_websocket_state.disconnect()
        mock_websocket_state.clear()
        await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass) is ready

    await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass)
    assert not _reauth_requested(hass, config_entry_setup)


@pytest.mark.parametrize(
    ("exception", "reauth"),
    [
        pytest.param(aiounifi.TwoFaTokenRequired, True, id="two_factor"),
        pytest.param(aiounifi.AuthenticationRateLimitError, False, id="rate_limited"),
    ],
)
async def test_login_answer_of_readiness_probe_after_login(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
    reauth: bool,
) -> None:
    """A probe after our login that answers like a login is handled like one."""
    hub = config_entry_setup.runtime_data
    probe = AsyncMock(side_effect=exception)
    with _expired_session(hub, probe=probe) as login:
        await mock_websocket_state.disconnect()
        mock_websocket_state.clear()
        await _advance(hass, FIRST_RETRY_DELAY)
        login.assert_called_once()
        assert _reauth_requested(hass, config_entry_setup) is reauth
        # Neither a rate limit nor a pending reauth retries within a minute
        await _advance(hass, MAX_RETRY_DELAY)

    probe.assert_called_once()
    assert not _available(hass)


@pytest.mark.parametrize(
    ("poll_error", "probe_error", "available"),
    [
        # Each transport failure of a poll checks the session
        pytest.param(
            aiounifi.LoginRequired, aiounifi.RequestError, False, id="login_required"
        ),
        pytest.param(TimeoutError, aiounifi.RequestError, False, id="timeout"),
        pytest.param(invalid_json(), aiounifi.RequestError, False, id="invalid_json"),
        # Each answer of the session check
        pytest.param(
            aiounifi.RequestError,
            aiounifi.RequestError,
            False,
            id="application_unreachable",
        ),
        pytest.param(aiounifi.RequestError, TimeoutError, False, id="probe_times_out"),
        pytest.param(aiounifi.RequestError, None, True, id="application_answers"),
        pytest.param(aiounifi.RequestError, KeyError, True, id="probe_broken"),
        pytest.param(
            aiounifi.RequestError,
            aiounifi.ResponseError,
            True,
            id="application_rejects",
        ),
        # The login aiounifi tried on its own was rejected, or the access is gone
        pytest.param(
            aiounifi.RequestError, aiounifi.Forbidden, False, id="login_rejected"
        ),
        pytest.param(
            aiounifi.RequestError, aiounifi.NoPermission, False, id="no_permission"
        ),
    ],
)
async def test_polling_transport_failure_checks_session(
    hass: HomeAssistant,
    hub: UnifiHub,
    polled_coordinator: UnifiDataUpdateCoordinator,
    poll_error: type[Exception],
    probe_error: type[Exception] | None,
    available: bool,
) -> None:
    """A failing poll only takes the session down when the probe fails too."""
    with (
        patch.object(polled_coordinator.handler, "update", side_effect=poll_error),
        patch.object(
            hub.api.system_information, "update", AsyncMock(side_effect=probe_error)
        ),
        patch.object(hub.api, "login") as login,
    ):
        await _advance(hass, IDLE_POLL_INTERVAL.total_seconds())

    assert _available(hass) is available
    assert not polled_coordinator.last_update_success
    login.assert_not_called()


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(aiounifi.Unauthorized, id="unauthorized"),
        pytest.param(aiounifi.Forbidden, id="forbidden"),
        pytest.param(aiounifi.NoPermission, id="no_permission"),
        pytest.param(aiounifi.ResponseError, id="response_error"),
    ],
)
async def test_polling_request_rejection_only_fails_coordinator(
    hass: HomeAssistant,
    hub: UnifiHub,
    polled_coordinator: UnifiDataUpdateCoordinator,
    exception: type[Exception],
) -> None:
    """A rejected poll needs no session check."""
    with (
        patch.object(polled_coordinator.handler, "update", side_effect=exception),
        patch.object(hub.api.system_information, "update") as probe,
    ):
        await _advance(hass, IDLE_POLL_INTERVAL.total_seconds())

    probe.assert_not_called()
    assert _available(hass)
    assert not polled_coordinator.last_update_success


async def test_polling_paused_while_connection_is_down(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    polled_coordinator: UnifiDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A poll in flight when the connection drops does not resume polling.

    Nothing is requested or logged while down, polling resumes after recovery.
    """
    hub = config_entry_setup.runtime_data
    calls: list[None] = []
    config_entry_setup.async_on_unload(
        polled_coordinator.async_add_listener(lambda: calls.append(None))
    )

    async def update_while_connection_drops() -> None:
        went_down = _availability_reached(hass, config_entry_setup, False)
        mock_websocket_state.set()
        await _wait(went_down)

    with (
        _expired_session(hub, AsyncMock(side_effect=aiounifi.RequestError)),
        patch.object(
            polled_coordinator.handler,
            "update",
            side_effect=update_while_connection_drops,
        ) as update,
    ):
        await _advance(hass, IDLE_POLL_INTERVAL.total_seconds())
        assert not _available(hass)
        requests = aioclient_mock.call_count
        calls.clear()
        await _advance(hass, (IDLE_POLL_INTERVAL * 2).total_seconds())

    update.assert_called_once()
    assert aioclient_mock.call_count == requests
    assert not calls
    assert polled_coordinator.last_update_success
    assert not _logged(caplog, logging.WARNING)

    mock_websocket_state.clear()
    await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass)
    assert calls

    calls.clear()
    await _advance(hass, IDLE_POLL_INTERVAL.total_seconds())
    assert calls


async def test_session_lost_during_recovery_retries_after_it(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A recovery that loses the session finishes first, then one login follows."""
    hub = config_entry_setup.runtime_data
    resync_started = asyncio.Event()
    resync_release = asyncio.Event()

    async def slow_update() -> None:
        resync_started.set()
        await resync_release.wait()
        # Fails once the session is already down, which needs no further check
        raise aiounifi.RequestError

    await mock_websocket_state.disconnect()
    went_down = _availability_reached(hass, config_entry_setup, False)
    with (
        _recovery_loses_session(hub) as (login, probe),
        patch.object(hub.api.devices, "update", side_effect=slow_update),
        patch.object(hub.api, "start_websocket") as start_websocket,
    ):
        _fire(hass, FIRST_RETRY_DELAY)
        await _wait(resync_started)
        await _wait(went_down)

        # The next retry falls due while the resync still runs
        _fire(hass, retry_window(1)[1] + 1)
        await hass.async_block_till_done()
        login.assert_called_once()

        resync_release.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    start_websocket.assert_not_called()
    assert probe.call_count == 2
    assert "Error fetching" not in caplog.text

    mock_websocket_state.clear()
    with _expired_session(hub) as login:
        await _advance(hass, MAX_RETRY_DELAY)
        await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass)
    login.assert_called_once()


async def test_hanging_recovery_is_retried(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Give up on a resync that does not finish and try again."""
    hub = config_entry_setup.runtime_data
    resync_started = asyncio.Event()

    async def hanging_update() -> None:
        resync_started.set()
        await asyncio.Event().wait()

    await mock_websocket_state.disconnect()
    mock_websocket_state.clear()
    with patch.object(hub.api.devices, "update", side_effect=hanging_update):
        _fire(hass, FIRST_RETRY_DELAY)
        await _wait(resync_started)
        assert _available(hass)

        # The timeout cancels the attempt, block_till_done skips cancelling tasks
        went_down = _availability_reached(hass, config_entry_setup, False)
        _fire(hass, RECOVERY_TIMEOUT + 1)
        await _wait(went_down)
        assert not _available(hass)

    await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass)


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(invalid_json(), id="invalid_json"),
        pytest.param(aiounifi.RequestError, id="request_error"),
        pytest.param(aiounifi.ResponseError, id="response_error"),
        pytest.param(aiounifi.Forbidden, id="forbidden"),
        pytest.param(aiounifi.NoPermission, id="no_permission"),
        pytest.param(KeyError, id="unexpected_error"),
    ],
)
async def test_failed_resync_of_reachable_application_keeps_session(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """Keep pushed data when one refetch fails but the application answers."""
    await mock_websocket_state.disconnect()
    mock_websocket_state.clear()
    with patch.object(hub.api.clients, "update", side_effect=exception):
        await _advance(hass, MAX_RETRY_DELAY)

    assert _available(hass)


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(aiounifi.WebsocketError, id="disconnected"),
        pytest.param(
            aiohttp.ClientConnectorError(Mock(), OSError()), id="connect_failed"
        ),
        pytest.param(aiohttp.WSServerHandshakeError(Mock(), ()), id="handshake_failed"),
    ],
)
async def test_websocket_error_marks_session_down(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    exception: Exception,
) -> None:
    """A websocket that fails after recovery takes the session down again."""
    await mock_websocket_state.disconnect()
    with patch.object(hub.api, "start_websocket", side_effect=exception):
        await _advance(hass, MAX_RETRY_DELAY)

    assert not _available(hass)


async def test_one_hanging_handler_does_not_block_recovery(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Give up on one stuck refetch and resume push updates anyway."""
    resync_started = asyncio.Event()
    websocket_started = asyncio.Event()

    async def hanging_update() -> None:
        resync_started.set()
        await asyncio.Event().wait()

    async def start_websocket() -> None:
        websocket_started.set()
        await asyncio.Event().wait()

    await mock_websocket_state.disconnect()
    with (
        patch.object(hub.api.port_forwarding, "update", side_effect=hanging_update),
        patch.object(hub.api, "start_websocket", side_effect=start_websocket),
    ):
        _fire(hass, FIRST_RETRY_DELAY)
        await _wait(resync_started)

        # The handler gives up before the whole recovery would
        _fire(hass, UPDATE_TIMEOUT + 1)
        await _wait(websocket_started)

    assert _available(hass)


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(aiounifi.ResponseError, id="response_error"),
        pytest.param(aiounifi.Forbidden, id="forbidden"),
    ],
)
async def test_rejected_websocket_handler_at_setup_loads_entry(
    config_entry_factory: ConfigEntryFactoryType,
    caplog: pytest.LogCaptureFixture,
    exception: type[Exception],
) -> None:
    """A websocket handler that cannot be listed at setup waits for pushes."""
    with patch("aiounifi.interfaces.clients.Clients.update", side_effect=exception):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.LOADED
    coordinator = config_entry.runtime_data.entity_loader.get_data_update_coordinator(
        config_entry.runtime_data.api.clients
    )
    assert coordinator.last_update_success
    assert "Error fetching UniFi Clients data" in caplog.text


@pytest.mark.parametrize("step", ["login", "probe"])
async def test_hanging_reconnect_step_is_given_up_and_retried(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    step: str,
) -> None:
    """A login or probe that never answers does not block reconnecting forever."""
    started = asyncio.Event()
    hanging = AsyncMock(side_effect=_hang_first_call(started))

    with _expired_session(config_entry_setup.runtime_data, **{step: hanging}):
        await mock_websocket_state.disconnect()
        _fire(hass, FIRST_RETRY_DELAY)
        await _wait(started)

        _fire(hass, REQUEST_TIMEOUT + 1)
        await hass.async_block_till_done()
        # Background tasks are not awaited, the hanging attempt may never end
        _fire(hass, MAX_RETRY_DELAY)
        await hass.async_block_till_done()

    assert hanging.call_count == 2


async def test_rate_limited_login_pauses_retries(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Wait for the login limit to pass instead of extending it, then go on."""
    hub = config_entry_setup.runtime_data
    login = AsyncMock(
        side_effect=[
            aiounifi.AuthenticationRateLimitError(),
            aiounifi.RequestError(),
            aiounifi.RequestError(),
        ]
    )
    limited = f"limits logins, pausing reconnects for {RATE_LIMIT_PAUSE} seconds"

    with _expired_session(hub, login):
        await mock_websocket_state.disconnect()
        await _advance(hass, FIRST_RETRY_DELAY)
        assert login.call_count == 1
        await _advance(hass, RATE_LIMIT_PAUSE - 1)
        assert login.call_count == 1
        await _advance(hass, RATE_LIMIT_PAUSE)
        assert login.call_count == 2
        # The pause was for the limit only, retries back off as usual again
        await _advance(hass, 1)
        assert login.call_count == 2
        await _advance(hass, MAX_RETRY_DELAY)
        assert login.call_count == 3
    assert caplog.text.count(limited) == 1

    mock_websocket_state.clear()
    with _expired_session(hub):
        await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass)
    assert not _reauth_requested(hass, config_entry_setup)

    with _expired_session(
        hub, AsyncMock(side_effect=aiounifi.AuthenticationRateLimitError)
    ):
        await mock_websocket_state.disconnect()
        await _advance(hass, MAX_RETRY_DELAY)
    assert caplog.text.count(limited) == 2


def _mock_expired_session(aioclient_mock: AiohttpClientMocker, **login: Any) -> None:
    """Answer requests with 401 and the login as given."""
    url = f"https://{DEFAULT_HOST}:{DEFAULT_PORT}"
    aioclient_mock.clear_requests()
    aioclient_mock.get(url, status=HTTPStatus.FOUND)
    aioclient_mock.get(
        f"{url}/api/s/{DEFAULT_SITE}/stat/sysinfo", status=HTTPStatus.UNAUTHORIZED
    )
    aioclient_mock.post(f"{url}/api/login", **login)


async def test_failed_relogin_of_aiounifi_does_not_restore_session(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A login aiounifi tries on its own for the expired session counts as rejected."""
    await mock_websocket_state.disconnect()
    _mock_expired_session(aioclient_mock, status=HTTPStatus.FORBIDDEN)

    for _ in range(2):
        await _advance(hass, MAX_RETRY_DELAY)
        assert not _available(hass)
        assert not _reauth_requested(hass, config_entry_setup)

    # The login of aiounifi counts as the first of three rejections in a row
    await _advance(hass, MAX_RETRY_DELAY)
    assert not _available(hass)
    assert _reauth_requested(hass, config_entry_setup)
    # aiounifi logged in on its own only once
    assert _login_requests(aioclient_mock) == 3


@pytest.mark.parametrize(
    ("exception", "logs_in", "available", "reauth"),
    [
        # The application is down or starting, the session outlives it
        pytest.param(aiounifi.ServiceUnavailable, False, False, False, id="starting"),
        pytest.param(aiounifi.BadGateway, False, False, False, id="bad_gateway"),
        pytest.param(aiounifi.RequestError, False, False, False, id="unreachable"),
        pytest.param(TimeoutError, False, False, False, id="timeout"),
        pytest.param(invalid_json(), False, False, False, id="invalid_json"),
        # The session expired
        pytest.param(aiounifi.LoginRequired, True, False, False, id="session_expired"),
        # An answer a fresh session tells apart
        pytest.param(aiounifi.ResponseError, True, True, False, id="response_error"),
        # Answers of the login aiounifi tried on its own, or a lost access
        pytest.param(aiounifi.Unauthorized, False, False, False, id="unauthorized"),
        pytest.param(aiounifi.Forbidden, False, False, False, id="forbidden"),
        pytest.param(aiounifi.NoPermission, False, False, False, id="no_permission"),
        pytest.param(
            aiounifi.AuthenticationRateLimitError,
            False,
            False,
            False,
            id="rate_limited",
        ),
        pytest.param(aiounifi.TwoFaTokenRequired, False, False, True, id="two_factor"),
    ],
)
async def test_first_probe_after_outage(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: Exception,
    logs_in: bool,
    available: bool,
    reauth: bool,
) -> None:
    """Only log in when the answer can mean the session expired."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()
    mock_websocket_state.clear()
    with (
        patch.object(hub.api, "login") as login,
        patch.object(hub.api.system_information, "update", side_effect=exception),
    ):
        await _advance(hass, FIRST_RETRY_DELAY)

    assert login.called is logs_in
    assert _available(hass) is available
    assert _reauth_requested(hass, config_entry_setup) is reauth


async def test_outage_after_reauth_healed_backs_off_as_usual(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Neither the reauth nor a rate limit during it slows down a later outage."""
    hub = config_entry_setup.runtime_data
    login = AsyncMock(
        side_effect=[
            aiounifi.TwoFaTokenRequired(),
            aiounifi.AuthenticationRateLimitError(),
        ]
    )
    with _expired_session(hub, login):
        await mock_websocket_state.disconnect()
        await _advance(hass, MAX_RETRY_DELAY)
        await _advance(hass, REAUTH_RETRY_INTERVAL)
        assert login.call_count == 2
    mock_websocket_state.clear()
    with _expired_session(hub):
        await _advance(hass, REAUTH_RETRY_INTERVAL)
    assert _available(hass)
    assert not _reauth_requested(hass, config_entry_setup)

    await _advance(hass, CONNECTION_STABLE_PERIOD)
    with _expired_session(hub, AsyncMock(side_effect=aiounifi.RequestError)) as login:
        await mock_websocket_state.disconnect()
        await _advance(hass, FIRST_RETRY_DELAY)
    login.assert_called_once()


@pytest.mark.parametrize(
    ("logins", "reauth"),
    [
        # The lock of a wrong password outlasts the pause
        pytest.param(
            [
                aiounifi.Forbidden(),
                aiounifi.Forbidden(),
                aiounifi.AuthenticationRateLimitError(),
                aiounifi.AuthenticationRateLimitError(),
            ],
            True,
            id="lock_outlasts_pause",
        ),
        # The limit of successful logins answers the same for a moment
        pytest.param(
            [
                aiounifi.Forbidden(),
                aiounifi.Forbidden(),
                aiounifi.AuthenticationRateLimitError(),
                None,
            ],
            False,
            id="limit_passes",
        ),
        pytest.param(
            [
                aiounifi.AuthenticationRateLimitError(),
                aiounifi.AuthenticationRateLimitError(),
                aiounifi.Forbidden(),
                aiounifi.Forbidden(),
            ],
            False,
            id="limited_before_rejections",
        ),
    ],
)
async def test_rate_limit_after_rejection_counts_as_rejection(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    logins: list[Exception | None],
    reauth: bool,
) -> None:
    """A wrong password that also locks the login still asks for reauth."""
    hub = config_entry_setup.runtime_data
    requested = False
    with _expired_session(hub, AsyncMock(side_effect=logins)) as login:
        await mock_websocket_state.disconnect()
        for _ in logins:
            await _advance(hass, MAX_RATE_LIMIT_PAUSE)
            requested |= _reauth_requested(hass, config_entry_setup)

    assert login.call_count == len(logins)
    assert requested is reauth


@pytest.mark.parametrize(
    "factor",
    [
        pytest.param(1 - RETRY_JITTER, id="early"),
        pytest.param(1 + RETRY_JITTER, id="late"),
    ],
)
async def test_retry_delay_is_jittered(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    factor: float,
) -> None:
    """Spread the retries so several entries don't log in at once."""
    with (
        patch(JITTER, return_value=factor) as uniform,
        _expired_session(
            hub,
            AsyncMock(
                side_effect=[aiounifi.AuthenticationRateLimitError(), KeyError()]
            ),
        ) as login,
    ):
        await mock_websocket_state.disconnect()
        for logins, delay in enumerate((RETRY_DELAYS[0], RATE_LIMIT_PAUSE)):
            await _advance(hass, delay * factor - 1)
            assert login.call_count == logins
            await _advance(hass, delay * factor + 1)
            assert login.call_count == logins + 1

    uniform.assert_called_with(1 - RETRY_JITTER, 1 + RETRY_JITTER)


async def test_drop_before_stable_period_keeps_backoff(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A connection that drops before it was stable does not reset the backoff later."""
    with (
        # Latest jitter, so the capped retry is due after the stable period
        patch(JITTER, return_value=1 + RETRY_JITTER),
        _expired_session(hub, AsyncMock(side_effect=aiounifi.RequestError)),
    ):
        await mock_websocket_state.disconnect()
        await _advance(hass, MAX_RETRY_DELAY)
        await _advance(hass, MAX_RETRY_DELAY)
    mock_websocket_state.clear()
    with _expired_session(hub):
        await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass)

    with (
        patch(JITTER, return_value=1 + RETRY_JITTER),
        _expired_session(hub, AsyncMock(side_effect=aiounifi.RequestError)) as login,
    ):
        await mock_websocket_state.disconnect()
        await _advance(hass, CONNECTION_STABLE_PERIOD)
        login.assert_not_called()
        await _advance(hass, MAX_RETRY_DELAY)
        await _advance(hass, FIRST_RETRY_DELAY)

    login.assert_called_once()


async def test_recovery_ending_down_keeps_backoff(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A recovery that is down when it ends does not reset the backoff later."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()
    went_down = _availability_reached(hass, config_entry_setup, False)

    async def devices_update() -> None:
        await _wait(went_down)

    with (
        # Latest jitter, so retries and the stable period fall due apart
        patch(JITTER, return_value=1 + RETRY_JITTER),
        _recovery_loses_session(
            hub, AsyncMock(side_effect=[None, *[aiounifi.RequestError()] * 5])
        ) as (login, _),
        patch.object(hub.api.devices, "update", side_effect=devices_update),
    ):
        await _advance(hass, FIRST_RETRY_DELAY)
        assert not _available(hass)
        await _advance(hass, retry_window(1)[1])
        assert login.call_count == 2
        await _advance(hass, CONNECTION_STABLE_PERIOD)
        assert login.call_count == 2
        await _advance(hass, MAX_RETRY_DELAY)
        assert login.call_count == 3
        await _advance(hass, FIRST_RETRY_DELAY)

    assert login.call_count == 3


@pytest.mark.parametrize(
    ("exception", "retry_delay"),
    [
        pytest.param(aiounifi.Forbidden, RETRY_DELAYS[0], id="rejected"),
        pytest.param(
            aiounifi.TwoFaTokenRequired, REAUTH_RETRY_INTERVAL, id="two_factor"
        ),
        pytest.param(
            aiounifi.AuthenticationRateLimitError, RATE_LIMIT_PAUSE, id="rate_limited"
        ),
    ],
)
async def test_login_answer_of_session_check_marks_session_down(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry_setup: MockConfigEntry,
    polled_coordinator: UnifiDataUpdateCoordinator,
    exception: type[Exception],
    retry_delay: float,
) -> None:
    """A login aiounifi tried on its own while polling is handled like ours."""
    hub = config_entry_setup.runtime_data
    with (
        patch.object(
            polled_coordinator.handler, "update", side_effect=aiounifi.RequestError
        ),
        patch.object(
            hub.api.system_information,
            "update",
            side_effect=_fail_first_call(exception()),
        ) as probe,
        patch.object(hub.api, "login") as login,
    ):
        await _advance(hass, IDLE_POLL_INTERVAL.total_seconds())
        assert not _available(hass)
        assert _reauth_requested(hass, config_entry_setup) is (
            exception is aiounifi.TwoFaTokenRequired
        )
        await _advance(hass, retry_delay - 1)
        assert probe.call_count == 1
        await _advance(hass, retry_delay)

    assert _available(hass)
    login.assert_not_called()
    assert caplog.text.count(LOST) == 1


async def test_rate_limit_pause_doubles_up_to_an_hour(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Wait longer while the limit holds, the console extends it on each try."""
    login = AsyncMock(side_effect=aiounifi.AuthenticationRateLimitError)
    with _expired_session(hub, login):
        await mock_websocket_state.disconnect()
        await _advance(hass, FIRST_RETRY_DELAY)
        for doubled in range(6):
            pause = min(RATE_LIMIT_PAUSE * 2**doubled, MAX_RATE_LIMIT_PAUSE)
            logins = login.call_count
            await _advance(hass, pause - 1)
            assert login.call_count == logins
            await _advance(hass, pause)
            assert login.call_count == logins + 1

    assert pause == MAX_RATE_LIMIT_PAUSE
    # Logged once while the limit holds
    assert caplog.text.count("limits logins") == 1


async def test_successful_login_ends_rejections_in_a_row(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Rejections before a working login don't count towards reauth."""
    hub = config_entry_setup.runtime_data
    login = AsyncMock(
        side_effect=[
            aiounifi.Forbidden(),
            aiounifi.Forbidden(),
            None,
            aiounifi.Forbidden(),
        ]
    )
    # The application is still starting after the working login, then the
    # session expires again
    probe = AsyncMock(side_effect=[aiounifi.RequestError(), aiounifi.LoginRequired()])
    with _expired_session(hub, login, probe):
        await mock_websocket_state.disconnect()
        for _ in range(4):
            await _advance(hass, MAX_RETRY_DELAY)

    assert login.call_count == 4
    assert not _reauth_requested(hass, config_entry_setup)


async def test_working_session_ends_rejections_in_a_row(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Rejections before a session that works again don't count towards reauth."""
    hub = config_entry_setup.runtime_data
    # The login aiounifi tries on its own is rejected twice, then the session
    # works again until the next outage
    probe = AsyncMock(
        side_effect=[
            aiounifi.Forbidden(),
            aiounifi.Forbidden(),
            None,
            aiounifi.Forbidden(),
        ]
    )
    with (
        patch.object(hub.api.system_information, "update", probe),
        patch.object(hub.api, "login") as login,
    ):
        await mock_websocket_state.disconnect()
        await _advance(hass, MAX_RETRY_DELAY)
        await _advance(hass, MAX_RETRY_DELAY)
        mock_websocket_state.clear()
        await _advance(hass, MAX_RETRY_DELAY)
        assert _available(hass)

        await mock_websocket_state.disconnect()
        await _advance(hass, MAX_RETRY_DELAY)

    assert probe.call_count == 4
    login.assert_not_called()
    assert not _reauth_requested(hass, config_entry_setup)


async def test_hanging_poll_checks_session(
    hass: HomeAssistant,
    hub: UnifiHub,
    polled_coordinator: UnifiDataUpdateCoordinator,
) -> None:
    """A poll that never answers is given up and checks the session."""
    started = asyncio.Event()
    with (
        patch.object(
            polled_coordinator.handler, "update", side_effect=_hang_first_call(started)
        ),
        patch.object(
            hub.api.system_information, "update", side_effect=aiounifi.RequestError
        ),
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await _wait(started)
        assert _available(hass)
        await _advance(hass, UPDATE_TIMEOUT + 1)

    assert not _available(hass)


async def test_rate_limit_pause_outlasts_slow_reauth_retries(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Retries while reauth is pending wait for the longer of both."""
    hub = config_entry_setup.runtime_data
    login = AsyncMock(
        side_effect=[
            aiounifi.TwoFaTokenRequired(),
            *[aiounifi.AuthenticationRateLimitError()] * 4,
        ]
    )
    with _expired_session(hub, login):
        await mock_websocket_state.disconnect()
        await _advance(hass, FIRST_RETRY_DELAY)
        await _advance(hass, REAUTH_RETRY_INTERVAL)
        # Pauses of 300 and 600 seconds are within the reauth interval
        await _advance(hass, REAUTH_RETRY_INTERVAL - 1)
        assert login.call_count == 2
        await _advance(hass, REAUTH_RETRY_INTERVAL)
        await _advance(hass, REAUTH_RETRY_INTERVAL)
        assert login.call_count == 4
        await _advance(hass, 4 * RATE_LIMIT_PAUSE - 1)
        assert login.call_count == 4
        await _advance(hass, 4 * RATE_LIMIT_PAUSE)

    assert login.call_count == 5


@pytest.mark.parametrize(
    ("logins", "probes"),
    [
        # Still starting after the working login, then that session expires
        pytest.param(
            [
                aiounifi.AuthenticationRateLimitError(),
                None,
                aiounifi.AuthenticationRateLimitError(),
                None,
            ],
            [
                aiounifi.ServiceUnavailable(),
                aiounifi.LoginRequired(),
                aiounifi.LoginRequired(),
                None,
            ],
            id="working_login",
        ),
        pytest.param(
            [
                aiounifi.AuthenticationRateLimitError(),
                aiounifi.RequestError(),
                aiounifi.AuthenticationRateLimitError(),
                None,
            ],
            [None],
            id="other_login_error",
        ),
    ],
)
async def test_rate_limit_pause_starts_over(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    logins: list[Exception | None],
    probes: list[Exception | None],
) -> None:
    """Only limits in a row double the pause."""
    login = AsyncMock(side_effect=logins)
    with _expired_session(hub, login, AsyncMock(side_effect=probes)):
        await mock_websocket_state.disconnect()
        mock_websocket_state.clear()
        await _advance(hass, FIRST_RETRY_DELAY)
        await _advance(hass, RATE_LIMIT_PAUSE)
        assert login.call_count == 2
        await _advance(hass, MAX_RETRY_DELAY)
        assert login.call_count == 3
        await _advance(hass, RATE_LIMIT_PAUSE)

    assert login.call_count == 4
    assert _available(hass)


async def test_rate_limit_ends_with_session_that_works_again(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A limit hit by aiounifi that passed starts the next pause over."""
    probe = AsyncMock(
        side_effect=[
            aiounifi.AuthenticationRateLimitError(),
            None,
            aiounifi.AuthenticationRateLimitError(),
            None,
        ]
    )
    with (
        patch.object(hub.api.system_information, "update", probe),
        patch.object(hub.api, "login") as login,
    ):
        await mock_websocket_state.disconnect()
        mock_websocket_state.clear()
        await _advance(hass, FIRST_RETRY_DELAY)
        await _advance(hass, RATE_LIMIT_PAUSE)
        assert _available(hass)

        # Back off as usual first, the stable period has not passed yet
        await mock_websocket_state.disconnect()
        await _advance(hass, MAX_RETRY_DELAY)
        mock_websocket_state.clear()
        await _advance(hass, RATE_LIMIT_PAUSE)

    assert _available(hass)
    login.assert_not_called()


async def test_rate_limit_seen_while_reconnecting_ends_with_it(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    polled_coordinator: UnifiDataUpdateCoordinator,
) -> None:
    """A limit the session check saw delays a queued retry, but not the next outage."""
    probe_started = asyncio.Event()
    probe_release = asyncio.Event()
    calls = 0

    async def limited_once() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            probe_started.set()
            await probe_release.wait()
            raise aiounifi.AuthenticationRateLimitError

    with (
        patch.object(
            polled_coordinator.handler, "update", side_effect=aiounifi.RequestError
        ),
        patch.object(hub.api.system_information, "update", side_effect=limited_once),
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await _wait(probe_started)
        # The websocket drops while the session check waits for its answer
        mock_websocket_state.set()
        await hass.async_block_till_done()
        probe_release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        mock_websocket_state.clear()
        await _advance(hass, MAX_RETRY_DELAY)
        assert not _available(hass)
        await _advance(hass, RATE_LIMIT_PAUSE)
    assert _available(hass)

    await _advance(hass, CONNECTION_STABLE_PERIOD)
    with patch.object(
        hub.api.system_information, "update", side_effect=aiounifi.RequestError
    ) as probe:
        await mock_websocket_state.disconnect()
        await _advance(hass, 1)
        probe.assert_not_called()
        await _advance(hass, FIRST_RETRY_DELAY)
    probe.assert_called_once()


async def test_failure_during_reconnect_attempt_needs_no_second_attempt(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A failure reported while an attempt runs is answered by that attempt."""
    probe_started = asyncio.Event()
    probe_release = asyncio.Event()
    calls = 0

    async def slow_first_probe() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            probe_started.set()
            await probe_release.wait()

    with (
        patch.object(
            hub.api.system_information, "update", side_effect=slow_first_probe
        ),
        patch.object(hub.entity_loader, "async_resync") as resync,
    ):
        hub.connection.report_failure()
        _fire(hass, MAX_RETRY_DELAY)
        await _wait(probe_started)
        # The websocket drops while the probe of the attempt is in flight
        mock_websocket_state.set()
        await hass.async_block_till_done()
        probe_release.set()
        mock_websocket_state.clear()
        await hass.async_block_till_done(wait_background_tasks=True)
        assert _available(hass)

        await _advance(hass, MAX_RETRY_DELAY)
        await _advance(hass, MAX_RETRY_DELAY)
    assert calls == 1
    resync.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "reauth"),
    [
        pytest.param(aiounifi.AuthenticationRateLimitError, False, id="rate_limited"),
        pytest.param(aiounifi.TwoFaTokenRequired, True, id="mfa"),
    ],
)
async def test_login_answer_of_poll_applies_its_policy(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    polled_coordinator: UnifiDataUpdateCoordinator,
    error: type[Exception],
    reauth: bool,
) -> None:
    """A poll that aiounifi logged in for applies the answer of that login."""
    hub = config_entry_setup.runtime_data
    with (
        patch.object(polled_coordinator.handler, "update", side_effect=error),
        patch.object(hub.api.system_information, "update") as probe,
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await hass.async_block_till_done(wait_background_tasks=True)
        assert not _available(hass)
        assert _reauth_requested(hass, config_entry_setup) is reauth

        await _advance(hass, MAX_RETRY_DELAY)
        probe.assert_not_called()


async def test_late_answer_of_older_session_check_is_dropped(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    polled_coordinator: UnifiDataUpdateCoordinator,
) -> None:
    """A reconnect replaces a session check that has not answered yet."""
    probe_started = asyncio.Event()
    probe_release = asyncio.Event()
    calls = 0

    async def slow_first_probe() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            probe_started.set()
            await probe_release.wait()
            raise aiounifi.RequestError

    with (
        patch.object(
            polled_coordinator.handler, "update", side_effect=aiounifi.RequestError
        ),
        patch.object(
            hub.api.system_information, "update", side_effect=slow_first_probe
        ),
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await _wait(probe_started)
        mock_websocket_state.set()
        await hass.async_block_till_done()
        mock_websocket_state.clear()
        await _advance(hass, MAX_RETRY_DELAY)
        assert _available(hass)

        probe_release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
    assert _available(hass)


async def test_reauth_after_rate_limit_delays_queued_retry(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    polled_coordinator: UnifiDataUpdateCoordinator,
) -> None:
    """A reauth that follows a rate limit pushes the queued retry back again."""
    hub = config_entry_setup.runtime_data
    probe_started = asyncio.Event()
    probe_release = asyncio.Event()
    calls = 0

    async def mfa_after_wait() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            probe_started.set()
            await probe_release.wait()
            raise aiounifi.TwoFaTokenRequired

    with (
        patch.object(
            polled_coordinator.handler, "update", side_effect=aiounifi.RequestError
        ),
        patch.object(hub.api.system_information, "update", side_effect=mfa_after_wait),
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await _wait(probe_started)
        # Another request saw aiounifi's own login being rate limited
        hub.connection.verify_session(aiounifi.AuthenticationRateLimitError())
        assert not _available(hass)
        probe_release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        assert _reauth_requested(hass, config_entry_setup)

        await _advance(hass, RATE_LIMIT_PAUSE + MAX_RETRY_DELAY)
        assert calls == 1
        await _advance(hass, REAUTH_RETRY_INTERVAL + MAX_RETRY_DELAY)
    assert calls > 1


async def test_rate_limit_answered_after_outage_pauses_queued_retry(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A request from before the outage that answers 429 late still pauses."""
    await mock_websocket_state.disconnect()
    assert not _available(hass)
    with patch.object(hub.api.system_information, "update") as probe:
        hub.connection.verify_session(aiounifi.AuthenticationRateLimitError())
        await _advance(hass, MAX_RETRY_DELAY)
        probe.assert_not_called()
        mock_websocket_state.clear()
        await _advance(hass, RATE_LIMIT_PAUSE + MAX_RETRY_DELAY)
    probe.assert_called_once()
    assert _available(hass)


async def test_late_rate_limits_within_pause_count_once(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Requests sent before a pause that answer 429 neither extend nor count it."""
    hub = config_entry_setup.runtime_data
    with patch.object(hub.api.system_information, "update") as probe:
        for _ in range(LOGIN_REJECTIONS_BEFORE_REAUTH):
            hub.connection.verify_session(aiounifi.AuthenticationRateLimitError())
        assert not _reauth_requested(hass, config_entry_setup)
        await _advance(hass, RATE_LIMIT_PAUSE)
    probe.assert_called_once()
    assert _available(hass)


async def test_unexpected_login_error_ends_rejections_in_a_row(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Rejections around an unexpected login error are not in a row."""
    hub = config_entry_setup.runtime_data
    login = AsyncMock(
        side_effect=[
            aiounifi.Forbidden,
            aiounifi.Forbidden,
            KeyError,
            aiounifi.Forbidden,
        ]
    )
    with _expired_session(hub, login):
        await mock_websocket_state.disconnect()
        for _ in range(4):
            await _advance(hass, MAX_RETRY_DELAY)
    assert login.call_count == 4
    assert not _reauth_requested(hass, config_entry_setup)


async def test_queued_resync_is_dropped_when_session_goes_down(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    polled_coordinator: UnifiDataUpdateCoordinator,
) -> None:
    """A resync waiting for an older poll does not run once the session is down."""
    poll_started = asyncio.Event()
    poll_release = asyncio.Event()
    calls = 0

    async def slow_first_poll() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            poll_started.set()
            await poll_release.wait()

    with patch.object(
        polled_coordinator.handler, "update", side_effect=slow_first_poll
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await _wait(poll_started)
        mock_websocket_state.set()
        await hass.async_block_till_done()
        mock_websocket_state.clear()
        # Within the timeout of the hanging poll
        _fire(hass, FIRST_RETRY_DELAY + 1)
        await hass.async_block_till_done()
        assert _available(hass)

        # The session goes down again while the resync waits for the poll
        hub.connection.report_failure()
        await hass.async_block_till_done()
        assert not _available(hass)
        poll_release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
    assert calls == 1


@PARAMETRIZE_STOP
async def test_session_check_in_flight_at_stop_is_cancelled(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    polled_coordinator: UnifiDataUpdateCoordinator,
    stop: Callable[[HomeAssistant, MockConfigEntry], Awaitable[None]],
) -> None:
    """Unload and shutdown don't leave a hanging session check behind."""
    hub = config_entry_setup.runtime_data
    probe_started = asyncio.Event()
    probe_cancelled = asyncio.Event()

    async def hang() -> None:
        probe_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            probe_cancelled.set()
            raise

    with (
        patch.object(
            polled_coordinator.handler, "update", side_effect=aiounifi.RequestError
        ),
        patch.object(hub.api.system_information, "update", side_effect=hang),
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await _wait(probe_started)
        await stop(hass, config_entry_setup)
        await hass.async_block_till_done()

    assert probe_cancelled.is_set()


async def test_unexpected_recovery_error_marks_session_down(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A recovery that breaks unexpectedly does not leave the session up."""
    await mock_websocket_state.disconnect()
    mock_websocket_state.clear()
    with patch.object(
        hub.entity_loader, "async_resync", side_effect=RuntimeError
    ) as resync:
        await _advance(hass, FIRST_RETRY_DELAY)
        resync.assert_called_once()
        assert not _available(hass)

    await _advance(hass, MAX_RETRY_DELAY)
    assert _available(hass)
