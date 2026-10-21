"""Test UniFi Network."""

import asyncio
from datetime import timedelta
from http import HTTPStatus
import logging
from types import MappingProxyType
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import aiounifi
from aiounifi import EndpointNotFound
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.models.message import MessageKey
import pytest

from homeassistant.components.unifi.const import CONF_BLOCK_CLIENT, DOMAIN
from homeassistant.components.unifi.coordinator import IDLE_POLL_INTERVAL, POLL_INTERVAL
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.components.unifi.hub import get_unifi_api
from homeassistant.components.unifi.hub.connection import (
    CONNECTION_STABLE_PERIOD,
    RECOVERY_TIMEOUT,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    EVENT_STATE_REPORTED,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import Event, EventStateReportedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from .conftest import (
    MAX_RETRY_DELAY,
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_hub_setup(
    device_registry: dr.DeviceRegistry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ) as forward_entry_setup:
        config_entry = await config_entry_factory()

    assert len(forward_entry_setup.mock_calls) == 1
    assert forward_entry_setup.mock_calls[0][1] == (
        config_entry,
        [
            Platform.BUTTON,
            Platform.DEVICE_TRACKER,
            Platform.IMAGE,
            Platform.LIGHT,
            Platform.SENSOR,
            Platform.SWITCH,
            Platform.UPDATE,
        ],
    )

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.unique_id)},
    )

    assert device_entry.sw_version == "7.4.162"


async def test_coordinators_preserve_handler_update_sources(
    config_entry_setup: MockConfigEntry,
) -> None:
    """Ensure coordinator polling matches the handler's existing update source."""
    loader = config_entry_setup.runtime_data.entity_loader
    api = config_entry_setup.runtime_data.api

    clients_coordinator = loader.get_data_update_coordinator(api.clients)
    devices_coordinator = loader.get_data_update_coordinator(api.devices)
    assert clients_coordinator.update_interval is None
    assert devices_coordinator.update_interval is None

    assert loader.get_data_update_coordinator(api.ports) is devices_coordinator
    assert loader.get_data_update_coordinator(api.outlets) is devices_coordinator

    for handler in (
        api.object_oriented_network_configs,
        api.traffic_rules,
        api.traffic_routes,
    ):
        coordinator = loader.get_data_update_coordinator(handler)
        assert coordinator.update_interval == IDLE_POLL_INTERVAL


async def test_get_data_update_coordinator_requires_registered_handler(
    config_entry_setup: MockConfigEntry,
) -> None:
    """Ensure a handler without a coordinator fails at lookup time."""
    loader = config_entry_setup.runtime_data.entity_loader
    api = config_entry_setup.runtime_data.api

    with pytest.raises(KeyError):
        loader.get_data_update_coordinator(api.sites)


async def test_polling_coordinator_refreshes_after_interval(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Ensure polling coordinators refresh when their interval elapses."""
    loader = config_entry_setup.runtime_data.entity_loader
    api = config_entry_setup.runtime_data.api
    coordinator = loader.get_data_update_coordinator(
        api.object_oriented_network_configs
    )

    assert coordinator.update_interval == IDLE_POLL_INTERVAL

    with patch.object(coordinator.handler, "items", return_value=[("id", object())]):
        await coordinator.async_refresh()

    assert coordinator.update_interval == POLL_INTERVAL

    with patch.object(
        api.object_oriented_network_configs,
        "update",
        wraps=api.object_oriented_network_configs.update,
    ) as mock_update:
        async_fire_time_changed(hass, dt_util.utcnow() + POLL_INTERVAL)
        await hass.async_block_till_done()

    assert mock_update.call_count >= 1


async def test_endpoint_not_found_disables_object_oriented_network_config_polling(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Ensure an unavailable optional endpoint stops polling after one warning."""
    loader = config_entry_setup.runtime_data.entity_loader
    api = config_entry_setup.runtime_data.api
    coordinator = loader.get_data_update_coordinator(
        api.object_oriented_network_configs
    )
    traffic_rules_coordinator = loader.get_data_update_coordinator(api.traffic_rules)

    with patch.object(
        coordinator.handler,
        "update",
        side_effect=EndpointNotFound("endpoint not found"),
    ) as mock_update:
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert coordinator.update_interval is None
        assert coordinator.last_update_success is False
        assert mock_update.call_count == 1

        async_fire_time_changed(hass, dt_util.utcnow() + POLL_INTERVAL)
        await hass.async_block_till_done()

        assert mock_update.call_count == 1

        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert mock_update.call_count == 2
    assert traffic_rules_coordinator.update_interval == IDLE_POLL_INTERVAL
    assert (
        caplog.text.count(
            "UniFi ObjectOrientedNetworkConfigs endpoint is unavailable; disabling polling"
        )
        == 1
    )


@pytest.mark.parametrize(
    "object_oriented_network_config_payload",
    [
        [
            {
                "id": "69f6b0a5e0e3ee2d4614cb5c",
                "enabled": True,
                "name": "Nintendo Switch - Block Internet",
                "target_type": "CLIENTS",
                "targets": ["00:00:00:00:00:01"],
                "qos": {"enabled": False},
                "route": {"enabled": False},
                "secure": {
                    "enabled": True,
                    "internet": {
                        "mode": "TURN_OFF_INTERNET",
                        "schedule": {"mode": "ALWAYS"},
                    },
                },
            }
        ]
    ],
)
async def test_entity_unavailable_on_polling_coordinator_failure(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Ensure polling failures make entities unavailable until recovery."""
    entity_id = "switch.unifi_network_nintendo_switch_block_internet"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"

    coordinator = (
        config_entry_setup.runtime_data.entity_loader.get_data_update_coordinator(
            config_entry_setup.runtime_data.api.object_oriented_network_configs
        )
    )

    with patch.object(
        coordinator.handler,
        "update",
        side_effect=RuntimeError("Polling error"),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"


@pytest.mark.parametrize(
    "exception",
    [aiounifi.ServiceUnavailable, TimeoutError, aiounifi.LoginRequired, ValueError],
)
async def test_setup_retries_when_network_application_not_ready(
    config_entry_factory: ConfigEntryFactoryType,
    exception: type[Exception],
) -> None:
    """Retry setup while the Network application cannot answer yet."""
    with patch(
        "aiounifi.interfaces.system_information.SystemInformationHandler.update",
        side_effect=exception,
    ):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("exception", [aiounifi.Forbidden, aiounifi.NoPermission])
async def test_setup_continues_when_system_information_is_rejected(
    config_entry_factory: ConfigEntryFactoryType,
    exception: type[Exception],
) -> None:
    """An application that rejects system information is up."""
    with patch(
        "aiounifi.interfaces.system_information.SystemInformationHandler.update",
        side_effect=exception,
    ):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.available


async def test_setup_retries_when_sites_unavailable(
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Ensure setup is retried when site information could not be loaded."""
    with patch(
        "aiounifi.interfaces.sites.Sites.update",
        side_effect=aiounifi.ServiceUnavailable,
    ):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_connection_recovery_does_not_restart_running_websocket(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Ensure recovery does not replace an active websocket consumer task."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )
    active_task = hub.websocket.ws_task
    assert active_task is not None

    with (
        patch.object(coordinator.handler, "update", side_effect=aiounifi.RequestError),
        patch.object(
            hub.api.system_information, "update", side_effect=aiounifi.RequestError
        ),
    ):
        assert coordinator.update_interval is not None
        async_fire_time_changed(hass, dt_util.utcnow() + coordinator.update_interval)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert not hub.available
    assert not active_task.done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hub.available
    assert hub.websocket.ws_task is active_task


@pytest.mark.parametrize("request_suffix", ["/stat/sta", "/stat/device"])
async def test_recovery_refetches_websocket_backed_handlers(
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    request_suffix: str,
) -> None:
    """Resync handlers fed by the websocket after the connection is restored."""

    def request_count() -> int:
        return sum(
            1
            for call in aioclient_mock.mock_calls
            if str(call[1]).endswith(request_suffix)
        )

    requests_before = request_count()

    await mock_websocket_state.disconnect()
    await mock_websocket_state.reconnect()

    assert request_count() == requests_before + 1


async def test_websocket_updates_notify_coordinator(
    config_entry_setup: MockConfigEntry,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Ensure websocket handler updates are forwarded through the coordinator."""
    coordinator = (
        config_entry_setup.runtime_data.entity_loader.get_data_update_coordinator(
            config_entry_setup.runtime_data.api.clients
        )
    )
    assert coordinator is not None

    with patch.object(
        coordinator, "async_set_updated_data", wraps=coordinator.async_set_updated_data
    ) as set_updated_data:
        mock_websocket_message(
            message=MessageKey.CLIENT,
            data={
                "hostname": "client",
                "ip": "10.0.0.1",
                "is_wired": True,
                "last_seen": 1562600145,
                "mac": "00:00:00:00:00:01",
                "name": "Client",
            },
        )

    set_updated_data.assert_called_once_with((ItemEvent.ADDED, "00:00:00:00:00:01"))


async def test_coordinator_filters_websocket_listeners_and_broadcasts_polling(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Ensure websocket updates filter listeners and polling updates broadcast."""
    clients_coordinator = (
        config_entry_setup.runtime_data.entity_loader.get_data_update_coordinator(
            config_entry_setup.runtime_data.api.clients
        )
    )
    client_calls: list[str] = []
    other_calls: list[str] = []

    @callback
    def client_listener() -> None:
        client_calls.append("called")

    @callback
    def other_listener() -> None:
        other_calls.append("called")

    remove_client_listener = clients_coordinator.async_add_listener(
        client_listener, context=("00:00:00:00:00:01",)
    )
    remove_other_listener = clients_coordinator.async_add_listener(
        other_listener, context=("00:00:00:00:00:02",)
    )

    mock_websocket_message(
        message=MessageKey.CLIENT,
        data={
            "hostname": "client",
            "ip": "10.0.0.1",
            "is_wired": True,
            "last_seen": 1562600145,
            "mac": "00:00:00:00:00:01",
            "name": "Client",
        },
    )

    assert client_calls == ["called"]
    assert other_calls == []

    polling_coordinator = (
        config_entry_setup.runtime_data.entity_loader.get_data_update_coordinator(
            config_entry_setup.runtime_data.api.object_oriented_network_configs
        )
    )
    polling_calls: list[str] = []
    other_polling_calls: list[str] = []

    @callback
    def polling_listener() -> None:
        polling_calls.append("called")

    @callback
    def other_polling_listener() -> None:
        other_polling_calls.append("called")

    remove_polling_listener = polling_coordinator.async_add_listener(
        polling_listener, context=("any-object",)
    )
    remove_other_polling_listener = polling_coordinator.async_add_listener(
        other_polling_listener, context=("another-object",)
    )
    polling_coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    assert polling_calls == ["called"]
    assert other_polling_calls == ["called"]

    remove_client_listener()
    remove_other_listener()
    remove_polling_listener()
    remove_other_polling_listener()


@pytest.mark.parametrize(
    "config_entry_options",
    [{CONF_BLOCK_CLIENT: ["00:00:00:00:00:01", "00:00:00:00:00:02"]}],
)
@pytest.mark.parametrize(
    "client_payload",
    [
        [
            {
                "blocked": True,
                "hostname": "client_1",
                "ip": "10.0.0.1",
                "is_wired": True,
                "last_seen": 1562600145,
                "mac": "00:00:00:00:00:01",
                "name": "Client 1",
            },
            {
                "blocked": True,
                "hostname": "client_2",
                "ip": "10.0.0.2",
                "is_wired": True,
                "last_seen": 1562600145,
                "mac": "00:00:00:00:00:02",
                "name": "Client 2",
            },
        ]
    ],
)
async def test_coordinator_update_only_refreshes_changed_entity(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Ensure a coordinator update for one object does not refresh unrelated entities."""
    changed_entity_id = "switch.client_1_blocked"
    other_entity_id = "switch.client_2_blocked"
    assert hass.states.get(changed_entity_id) is not None
    assert hass.states.get(other_entity_id) is not None

    written_entity_ids: list[str] = []

    @callback
    def track_state_reported(event: Event[EventStateReportedData]) -> None:
        written_entity_ids.append(event.data["entity_id"])

    @callback
    def filter_tracked_entities(data: EventStateReportedData) -> bool:
        return data["entity_id"] in (changed_entity_id, other_entity_id)

    hass.bus.async_listen(
        EVENT_STATE_REPORTED, track_state_reported, filter_tracked_entities
    )

    mock_websocket_message(
        message=MessageKey.CLIENT,
        data={
            "hostname": "client_1",
            "ip": "10.0.0.1",
            "is_wired": True,
            "last_seen": 1562600146,
            "mac": "00:00:00:00:00:01",
            "name": "Client 1",
        },
    )
    await hass.async_block_till_done()

    assert changed_entity_id in written_entity_ids
    assert other_entity_id not in written_entity_ids


async def test_reset_after_successful_setup(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Calling reset when the entry has been setup."""
    assert config_entry_setup.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry_setup.entry_id)
    assert config_entry_setup.state is ConfigEntryState.NOT_LOADED


async def test_reset_fails(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Calling reset when the entry has been setup can return false."""
    assert config_entry_setup.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(config_entry_setup.entry_id)
        assert config_entry_setup.state is ConfigEntryState.FAILED_UNLOAD


@pytest.mark.usefixtures("mock_device_registry")
async def test_connection_state_signalling(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_state: WebsocketStateManager,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify connection statesignalling and connection state are working."""
    client_payload.append(
        {
            "hostname": "client",
            "ip": "10.0.0.1",
            "is_wired": True,
            "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
            "mac": "00:00:00:00:00:01",
        }
    )
    await config_entry_factory()

    # Controller is connected
    assert hass.states.get("device_tracker.client").state == "home"

    await mock_websocket_state.disconnect()
    # Controller is disconnected
    assert hass.states.get("device_tracker.client").state == "unavailable"

    await mock_websocket_state.reconnect()
    # Controller is once again connected
    assert hass.states.get("device_tracker.client").state == "home"


async def test_reconnect_mechanism(
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Verify reconnect prints only on first reconnection try."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234/",
        status=HTTPStatus.BAD_GATEWAY,
    )

    await mock_websocket_state.disconnect()
    assert aioclient_mock.call_count == 0

    await mock_websocket_state.reconnect(fail=True)
    assert aioclient_mock.call_count == 1

    await mock_websocket_state.reconnect(fail=True)
    assert aioclient_mock.call_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError,
        aiounifi.AuthenticationRateLimitError,
        aiounifi.BadGateway,
        aiounifi.ServiceUnavailable,
        aiounifi.AiounifiException,
    ],
)
async def test_reconnect_mechanism_exceptions(
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """Keep retrying the login after errors that are not about credentials."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()

    with patch.object(hub.api, "login", side_effect=exception) as login:
        await mock_websocket_state.reconnect(fail=True)
    login.assert_called_once()
    assert not hub.available

    await mock_websocket_state.reconnect()
    assert hub.available


@pytest.mark.parametrize(
    ("side_effect", "raised_exception"),
    [
        (TimeoutError, CannotConnect),
        (aiounifi.BadGateway, CannotConnect),
        (aiounifi.Forbidden, CannotConnect),
        (aiounifi.ServiceUnavailable, CannotConnect),
        (aiounifi.RequestError, CannotConnect),
        (aiounifi.ResponseError, CannotConnect),
        (aiounifi.Unauthorized, AuthenticationRequired),
        (aiounifi.LoginRequired, AuthenticationRequired),
        (aiounifi.AiounifiException, AuthenticationRequired),
    ],
)
async def test_get_unifi_api_fails_to_connect(
    hass: HomeAssistant,
    side_effect: Exception,
    raised_exception: Exception,
    config_entry_data: MappingProxyType[str, Any],
) -> None:
    """Check that get_unifi_api can handle UniFi Network being unavailable."""
    with (
        patch("aiounifi.Controller.login", side_effect=side_effect),
        pytest.raises(raised_exception),
    ):
        await get_unifi_api(hass, config_entry_data)


WIRELESS_CLIENT = {
    "ap_mac": "00:00:00:00:02:01",
    "essid": "ssid",
    "hostname": "client_1",
    "ip": "10.0.0.1",
    "is_wired": False,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:01",
}


async def test_unexpected_error_during_resync_keeps_retrying(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Mark the hub down and retry when the resync fails unexpectedly."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()

    with patch.object(hub.api.clients, "update", side_effect=KeyError):
        await mock_websocket_state.reconnect()
    assert not hub.available

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hub.available
    assert not hub.websocket.ws_task.done()


async def test_poll_in_flight_does_not_resume_polling_while_down(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A poll that ends after the connection dropped keeps polling paused."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )
    updates = 0

    async def update_while_connection_drops() -> None:
        nonlocal updates
        updates += 1
        hub.connection.report_failure()

    with (
        patch.object(hub.api, "login", side_effect=aiounifi.RequestError),
        patch.object(
            coordinator.handler, "update", side_effect=update_while_connection_drops
        ),
    ):
        assert coordinator.update_interval is not None
        async_fire_time_changed(hass, dt_util.utcnow() + coordinator.update_interval)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert not hub.available

        async_fire_time_changed(hass, dt_util.utcnow() + IDLE_POLL_INTERVAL * 2)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert updates == 1
    assert "Error fetching" not in caplog.text


async def _advance(hass: HomeAssistant, seconds: float) -> None:
    """Fire timers due within the given number of seconds."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_reconnect_backoff_grows_caps_and_resets(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Retry later after each failed login and start over once stable."""
    hub = config_entry_setup.runtime_data

    with patch.object(hub.api, "login", side_effect=aiounifi.RequestError) as login:
        await mock_websocket_state.disconnect()
        # Jitter spreads each delay by 20 percent: 15 s, 30 s, then capped at 60 s
        for earliest, latest, attempts in ((11, 18, 1), (23, 36, 2), (47, 72, 3)):
            await _advance(hass, earliest)
            assert login.call_count == attempts - 1
            await _advance(hass, latest)
            assert login.call_count == attempts
        await _advance(hass, 47)
        assert login.call_count == 3
        await _advance(hass, 72)
        assert login.call_count == 4

    mock_websocket_state.clear()
    await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available

    # Only a connection that stayed up starts the backoff over
    await _advance(hass, CONNECTION_STABLE_PERIOD)
    with patch.object(hub.api, "login", side_effect=aiounifi.RequestError) as login:
        await mock_websocket_state.disconnect()
        await _advance(hass, 18)
    login.assert_called_once()


async def test_backoff_survives_flapping_connection(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A connection that drops again before it was stable keeps backing off."""
    hub = config_entry_setup.runtime_data

    with patch.object(hub.api, "login", side_effect=aiounifi.RequestError):
        await mock_websocket_state.disconnect()
        await _advance(hass, 18)
    mock_websocket_state.clear()
    with patch.object(hub.api, "login", AsyncMock()):
        await _advance(hass, 36)
    assert hub.available

    with patch.object(hub.api, "login", side_effect=aiounifi.RequestError) as login:
        await mock_websocket_state.disconnect()
        # Also passes the stable period of the short lived recovery
        await _advance(hass, MAX_RETRY_DELAY)
        await _advance(hass, MAX_RETRY_DELAY)
        assert login.call_count == 2
        await _advance(hass, 47)
    assert login.call_count == 2


async def test_concurrent_failures_schedule_one_retry(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Several failure sources lead to a single login attempt."""
    hub = config_entry_setup.runtime_data

    with patch.object(hub.api, "login", side_effect=aiounifi.RequestError) as login:
        await mock_websocket_state.disconnect()
        hub.connection.report_failure()
        hub.connection.report_failure()
        await _advance(hass, 18)

    login.assert_called_once()
    assert caplog.text.count("Connection to UniFi Network lost") == 1


async def test_no_retry_after_unload(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """A failure reported after unload neither retries nor changes state."""
    hub = config_entry_setup.runtime_data
    assert await hass.config_entries.async_unload(config_entry_setup.entry_id)

    with patch.object(hub.api, "login") as login:
        hub.connection.report_failure()
        await _advance(hass, MAX_RETRY_DELAY)

    login.assert_not_called()
    assert hub.available


async def test_unload_during_login_does_not_retry(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """An attempt cancelled by unload does not schedule another one."""
    hub = config_entry_setup.runtime_data
    login_started = asyncio.Event()

    async def hanging_login() -> None:
        login_started.set()
        await asyncio.Event().wait()

    with patch.object(hub.api, "login", side_effect=hanging_login) as login:
        await mock_websocket_state.disconnect()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=18))
        await login_started.wait()

        assert await hass.config_entries.async_unload(config_entry_setup.entry_id)
        await _advance(hass, MAX_RETRY_DELAY)

    login.assert_called_once()


async def test_failed_setup_does_not_retry(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Nothing keeps logging in after setup failed."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        side_effect=RuntimeError,
    ):
        config_entry = await config_entry_factory()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    with patch("aiounifi.Controller.login") as login:
        config_entry.runtime_data.connection.report_failure()
        await _advance(hass, MAX_RETRY_DELAY)

    login.assert_not_called()


@pytest.mark.parametrize(
    "exception",
    [
        aiounifi.LoginRequired,
        aiounifi.NoPermission,
        aiounifi.TwoFaTokenRequired,
        aiounifi.Unauthorized,
    ],
)
async def test_rejected_login_starts_reauth_and_stops_retrying(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """Only the user can fix rejected credentials, so stop logging in."""
    hub = config_entry_setup.runtime_data

    with patch.object(hub.api, "login", side_effect=exception) as login:
        await mock_websocket_state.disconnect()
        await _advance(hass, MAX_RETRY_DELAY)
        await _advance(hass, MAX_RETRY_DELAY)

    login.assert_called_once()
    assert not hub.available
    assert list(config_entry_setup.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    ("exception", "ready"),
    [
        pytest.param(aiounifi.ServiceUnavailable, False, id="starting"),
        pytest.param(aiounifi.RequestError, False, id="unreachable"),
        pytest.param(TimeoutError, False, id="timeout"),
        pytest.param(aiounifi.LoginRequired, False, id="session_expired"),
        pytest.param(aiounifi.Unauthorized, False, id="unauthorized"),
        pytest.param(aiounifi.TwoFaTokenRequired, False, id="two_factor"),
        pytest.param(ValueError, False, id="malformed_answer"),
        pytest.param(KeyError, False, id="unexpected_error"),
        pytest.param(aiounifi.Forbidden, True, id="forbidden"),
        pytest.param(aiounifi.NoPermission, True, id="no_permission"),
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

    with (
        patch.object(hub.api, "login", AsyncMock()),
        patch.object(hub.api.system_information, "update", side_effect=exception),
    ):
        await mock_websocket_state.disconnect()
        mock_websocket_state.clear()
        await _advance(hass, MAX_RETRY_DELAY)
        assert hub.available is ready

    await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available
    assert not list(config_entry_setup.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    "poll_error",
    [
        aiounifi.RequestError,
        aiounifi.BadGateway,
        aiounifi.ServiceUnavailable,
        TimeoutError,
    ],
)
@pytest.mark.parametrize(
    ("probe_error", "available"),
    [
        pytest.param(None, True, id="application_answers"),
        pytest.param(aiounifi.Forbidden, True, id="application_rejects"),
        pytest.param(KeyError, True, id="probe_broken"),
        pytest.param(aiounifi.RequestError, False, id="application_unreachable"),
    ],
)
async def test_polling_transport_failure_checks_session(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    poll_error: type[Exception],
    probe_error: type[Exception] | None,
    available: bool,
) -> None:
    """A failing poll only takes the session down when the probe fails too."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )

    with (
        patch.object(coordinator.handler, "update", side_effect=poll_error),
        patch.object(
            hub.api.system_information, "update", AsyncMock(side_effect=probe_error)
        ),
    ):
        assert coordinator.update_interval is not None
        await _advance(hass, coordinator.update_interval.total_seconds())

    assert hub.available is available
    assert not coordinator.last_update_success


@pytest.mark.parametrize(
    "exception",
    [
        aiounifi.LoginRequired,
        aiounifi.Unauthorized,
        aiounifi.Forbidden,
        aiounifi.NoPermission,
        aiounifi.ResponseError,
    ],
)
async def test_polling_request_rejection_only_fails_coordinator(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    exception: type[Exception],
) -> None:
    """A rejected poll needs no session check."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )

    with (
        patch.object(coordinator.handler, "update", side_effect=exception),
        patch.object(hub.api.system_information, "update") as probe,
    ):
        assert coordinator.update_interval is not None
        await _advance(hass, coordinator.update_interval.total_seconds())

    probe.assert_not_called()
    assert hub.available
    assert not coordinator.last_update_success


async def test_polling_paused_while_connection_is_down(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Send no requests and log nothing while down, resume after recovery."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )
    calls: list[None] = []
    coordinator.async_add_listener(lambda: calls.append(None))

    with patch.object(hub.api, "login", side_effect=aiounifi.RequestError):
        await mock_websocket_state.disconnect()
        requests = aioclient_mock.call_count
        calls.clear()
        await _advance(hass, (IDLE_POLL_INTERVAL * 2).total_seconds())

    assert aioclient_mock.call_count == requests
    assert not calls
    assert coordinator.last_update_success
    assert not [
        record for record in caplog.records if record.levelno >= logging.WARNING
    ]

    mock_websocket_state.clear()
    await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available
    assert calls

    calls.clear()
    await _advance(hass, IDLE_POLL_INTERVAL.total_seconds())
    assert calls


async def test_failure_during_recovery_retries_after_recovery(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Retry when the application goes away while the resync is still running."""
    hub = config_entry_setup.runtime_data
    resync_release = asyncio.Event()
    went_down = asyncio.Event()

    async def slow_update() -> None:
        await resync_release.wait()

    await mock_websocket_state.disconnect()

    @callback
    def _connection_changed() -> None:
        if not hub.available:
            went_down.set()

    config_entry_setup.async_on_unload(
        async_dispatcher_connect(hass, hub.signal_reachable, _connection_changed)
    )
    with (
        patch.object(hub.api, "login", AsyncMock()),
        # The readiness probe passes, the check after the failed refetch does not
        patch.object(
            hub.api.system_information,
            "update",
            AsyncMock(side_effect=[None, aiounifi.RequestError()]),
        ),
        patch.object(hub.api.clients, "update", side_effect=aiounifi.RequestError),
        patch.object(hub.api.devices, "update", side_effect=slow_update),
        patch.object(hub.api, "start_websocket") as start_websocket,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=18))
        await went_down.wait()
        assert not hub.available

        # The next retry falls due while the resync is still in flight
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=40))
        resync_release.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    start_websocket.assert_not_called()
    assert "Error fetching" not in caplog.text

    mock_websocket_state.clear()
    await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available


async def test_hanging_recovery_is_retried(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Give up on a resync that does not finish and try again."""
    hub = config_entry_setup.runtime_data
    resync_started = asyncio.Event()
    connection_changed = asyncio.Event()

    @callback
    def _connection_changed() -> None:
        connection_changed.set()

    config_entry_setup.async_on_unload(
        async_dispatcher_connect(hass, hub.signal_reachable, _connection_changed)
    )

    async def hanging_update() -> None:
        resync_started.set()
        await asyncio.Event().wait()

    await mock_websocket_state.disconnect()
    mock_websocket_state.clear()
    with patch.object(hub.api.devices, "update", side_effect=hanging_update):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=18))
        await resync_started.wait()
        assert hub.available

        # The timeout cancels the attempt, block_till_done skips cancelling tasks
        connection_changed.clear()
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=RECOVERY_TIMEOUT + 1)
        )
        await connection_changed.wait()
        assert not hub.available

    await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError,
        aiounifi.RequestError,
        aiounifi.ResponseError,
        aiounifi.Forbidden,
        aiounifi.NoPermission,
    ],
)
@pytest.mark.parametrize("client_payload", [[WIRELESS_CLIENT]])
@pytest.mark.usefixtures("mock_device_registry")
async def test_failed_resync_of_reachable_application_keeps_session(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """Keep pushed data when one refetch fails but the application answers."""
    hub = config_entry_setup.runtime_data

    await mock_websocket_state.disconnect()
    mock_websocket_state.clear()
    with (
        patch.object(hub.api, "login", AsyncMock()),
        patch.object(hub.api.clients, "update", side_effect=exception),
    ):
        await _advance(hass, MAX_RETRY_DELAY)

    assert hub.available
    assert hass.states.get("device_tracker.client_1").state != STATE_UNAVAILABLE


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
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: Exception,
) -> None:
    """A websocket that fails after recovery takes the session down again."""
    hub = config_entry_setup.runtime_data

    await mock_websocket_state.disconnect()
    with (
        patch.object(hub.api, "login", AsyncMock()),
        patch.object(hub.api, "start_websocket", side_effect=exception),
    ):
        await _advance(hass, MAX_RETRY_DELAY)

    assert not hub.available


async def test_simultaneous_polling_failures_check_session_once(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Several endpoints failing together share one session check."""
    hub = config_entry_setup.runtime_data
    probe_started = asyncio.Event()
    probe_release = asyncio.Event()

    async def slow_probe() -> None:
        probe_started.set()
        await probe_release.wait()

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
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + IDLE_POLL_INTERVAL)
        await probe_started.wait()
        await hass.async_block_till_done()
        probe_release.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    probe.assert_called_once()
    assert hub.available
