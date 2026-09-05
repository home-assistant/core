"""Tests for the Beatbot cloud event bridge."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Protocol
from unittest.mock import AsyncMock, Mock

from beatbot_cloud import BeatbotAuthenticationError, BeatbotEvent
import pytest

from homeassistant.components.beatbot import event_stream as event_stream_module
from homeassistant.components.beatbot.event_stream import BeatbotEventClient
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError


class EventFactory(Protocol):
    """Create a validated Beatbot event."""

    def __call__(
        self,
        event_id: str,
        event_type: str,
        payload: dict | None,
        device_id: str = "dev-1",
    ) -> BeatbotEvent:
        """Create one Beatbot event."""


@pytest.fixture(autouse=True)
def mock_client_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the shared aiohttp session."""
    monkeypatch.setattr(
        event_stream_module,
        "async_get_clientsession",
        Mock(return_value=SimpleNamespace()),
    )


@pytest.fixture
def event_client(hass: HomeAssistant) -> tuple[BeatbotEventClient, Mock]:
    """Return an event client and its coordinator."""
    coordinator = Mock()
    client = BeatbotEventClient(
        hass,
        SimpleNamespace(entry_id="entry"),
        SimpleNamespace(),
        SimpleNamespace(
            event_stream_url="ws://example/events",
            async_get_access_token=AsyncMock(return_value="token"),
        ),
        coordinator,
    )
    return client, coordinator


@pytest.fixture
def event_factory() -> EventFactory:
    """Return a Beatbot event factory."""

    def _event(
        event_id: str,
        event_type: str,
        payload: dict | None,
        device_id: str = "dev-1",
    ) -> BeatbotEvent:
        return BeatbotEvent(event_id, event_type, device_id, payload)

    return _event


def test_start_registers_entry_background_task(hass: HomeAssistant) -> None:
    """The lifetime event client must not block Home Assistant startup."""
    task = Mock()
    entry = SimpleNamespace(
        entry_id="entry",
        async_create_background_task=Mock(return_value=task),
    )
    client = BeatbotEventClient(
        hass,
        entry,
        SimpleNamespace(),
        SimpleNamespace(
            event_stream_url="ws://example/events",
            async_get_access_token=AsyncMock(return_value="token"),
        ),
        Mock(),
    )

    try:
        client.async_start()
        call_args = entry.async_create_background_task.call_args.args
    finally:
        entry.async_create_background_task.call_args.args[1].close()

    entry.async_create_background_task.assert_called_once()
    assert call_args[0] is hass
    assert call_args[1].cr_code is BeatbotEventClient._run.__code__
    assert call_args[2] == "beatbot_event_stream_entry"
    assert client._task is task


@pytest.mark.parametrize("event_type", ["properties_changed", "status"])
def test_state_event_routes_incremental_state(
    event_client: tuple[BeatbotEventClient, Mock],
    event_factory: EventFactory,
    event_type: str,
) -> None:
    """Route state-bearing events to the coordinator."""
    client, coordinator = event_client
    event = event_factory("event-1", event_type, {"online": False})

    client._handle_event(event)

    coordinator.async_apply_device_event.assert_called_once_with(event)


def test_unknown_event_does_not_route(
    event_client: tuple[BeatbotEventClient, Mock], event_factory: EventFactory
) -> None:
    """Ignore unsupported events returned by the library."""
    client, coordinator = event_client

    client._handle_event(event_factory("event-2", "future_type", {}))

    coordinator.async_apply_device_event.assert_not_called()


async def test_library_authentication_error_starts_reauth(
    hass: HomeAssistant, event_client: tuple[BeatbotEventClient, Mock]
) -> None:
    """Start reauthentication when the library reports terminal auth failure."""
    client, _ = event_client
    client._client.async_run = AsyncMock(side_effect=BeatbotAuthenticationError)
    client._entry.async_start_reauth = Mock()

    await client._run()

    client._entry.async_start_reauth.assert_called_once_with(hass)


@pytest.mark.parametrize("event_type", ["device_added", "device_removed"])
def test_topology_event_reloads_entry(
    hass: HomeAssistant,
    event_client: tuple[BeatbotEventClient, Mock],
    event_factory: EventFactory,
    event_type: str,
) -> None:
    """Reload the entry after a device topology event."""
    client, coordinator = event_client
    hass.config_entries.async_schedule_reload = Mock()
    payload = None if event_type == "device_removed" else {"deviceId": "dev-1"}

    client._handle_event(event_factory("event-3", event_type, payload))

    hass.config_entries.async_schedule_reload.assert_called_once_with("entry")
    coordinator.async_apply_device_event.assert_not_called()


async def test_stop_is_idempotent(
    event_client: tuple[BeatbotEventClient, Mock],
) -> None:
    """Allow the event client to be stopped repeatedly."""
    client, _ = event_client
    client._client.async_close = AsyncMock()

    await client.async_stop()
    await client.async_stop()

    assert client._client.async_close.await_count == 2


async def test_rejected_token_is_refreshed_only_once(hass: HomeAssistant) -> None:
    """Refresh a rejected access token only if it is still current."""
    entry = SimpleNamespace(
        entry_id="entry",
        data={"token": {"access_token": "old", "refresh_token": "refresh"}},
    )
    oauth_session = SimpleNamespace(token=entry.data["token"])

    async def _ensure_token_valid() -> None:
        oauth_session.token = {
            "access_token": "new",
            "refresh_token": "refresh",
        }

    oauth_session.async_ensure_token_valid = AsyncMock(side_effect=_ensure_token_valid)
    client = BeatbotEventClient(
        hass,
        entry,
        oauth_session,
        SimpleNamespace(
            event_stream_url="ws://example/events",
            async_get_access_token=AsyncMock(return_value="token"),
        ),
        Mock(),
    )
    hass.config_entries.async_update_entry = Mock()

    assert await client._async_refresh_token("old") == "new"
    assert await client._async_refresh_token("old") == "new"

    oauth_session.async_ensure_token_valid.assert_awaited_once()


async def test_terminal_refresh_error_is_translated(
    hass: HomeAssistant, event_client: tuple[BeatbotEventClient, Mock]
) -> None:
    """Translate a terminal OAuth refresh failure for the client library."""
    client, _ = event_client
    client._oauth_session.token = {"access_token": "old"}
    client._oauth_session.async_ensure_token_valid = AsyncMock(
        side_effect=OAuth2TokenRequestReauthError(
            request_info=SimpleNamespace(real_url="https://oauth.beatbot.com/token"),
            status=400,
            domain="beatbot",
        )
    )
    client._entry.data = {"token": client._oauth_session.token}
    hass.config_entries.async_update_entry = Mock()

    with pytest.raises(BeatbotAuthenticationError):
        await client._async_refresh_token("old")


def test_library_callbacks_are_registered(
    event_client: tuple[BeatbotEventClient, Mock],
) -> None:
    """Register Home Assistant callbacks with the client library."""
    client, coordinator = event_client

    assert client._client._event_callback == client._handle_event
    assert client._client._reconnect_callback == coordinator.async_request_refresh
    assert client._client._token_refresh_callback == client._async_refresh_token
