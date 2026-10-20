"""Test UniFi Network."""

import asyncio
from datetime import timedelta
from http import HTTPStatus
import logging
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

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
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    EVENT_STATE_REPORTED,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import Event, EventStateReportedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import (
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


TRANSPORT_ERRORS = [
    aiounifi.RequestError,
    aiounifi.BadGateway,
    aiounifi.ServiceUnavailable,
    TimeoutError,
]


@pytest.mark.parametrize("exception", TRANSPORT_ERRORS)
@pytest.mark.parametrize(
    "probe_error",
    [
        pytest.param(aiounifi.RequestError, id="probe_unreachable"),
        pytest.param(KeyError, id="probe_malformed"),
    ],
)
async def test_polling_transport_failure_with_unresponsive_application(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    exception: type[Exception],
    probe_error: type[Exception],
) -> None:
    """Mark the hub unavailable when the readiness probe fails as well."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )

    with (
        patch.object(coordinator.handler, "update", side_effect=exception),
        patch.object(hub.api.system_information, "update", side_effect=probe_error),
    ):
        assert coordinator.update_interval is not None
        async_fire_time_changed(hass, dt_util.utcnow() + coordinator.update_interval)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert not hub.available


@pytest.mark.parametrize("exception", TRANSPORT_ERRORS)
async def test_polling_transport_failure_of_one_endpoint(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    exception: type[Exception],
) -> None:
    """Only fail the coordinator when the Network application still answers."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )

    with patch.object(coordinator.handler, "update", side_effect=exception):
        assert coordinator.update_interval is not None
        async_fire_time_changed(hass, dt_util.utcnow() + coordinator.update_interval)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hub.available
    assert coordinator.last_update_success is False


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
async def test_polling_request_rejection_does_not_report_connection_failure(
    config_entry_setup: MockConfigEntry,
    exception: type[Exception],
) -> None:
    """Ensure rejected polling requests only fail the coordinator."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )

    with (
        patch.object(
            coordinator.handler,
            "update",
            side_effect=exception,
        ),
        patch.object(
            hub.connection,
            "report_failure",
            wraps=hub.connection.report_failure,
        ) as report_failure,
    ):
        assert coordinator.update_interval is not None
        async_fire_time_changed(
            hub.hass, dt_util.utcnow() + coordinator.update_interval
        )
        await hub.hass.async_block_till_done()

    report_failure.assert_not_called()
    assert hub.available
    assert coordinator.last_update_success is False


async def test_startup_network_information_failure_reports_connection_failure(
    config_entry_setup: MockConfigEntry,
) -> None:
    """Ensure startup-only required API failures mark the shared connection down."""
    hub = config_entry_setup.runtime_data

    with (
        patch.object(
            hub.api.system_information,
            "update",
            side_effect=aiounifi.ServiceUnavailable,
        ),
        patch.object(
            hub.connection,
            "report_failure",
            wraps=hub.connection.report_failure,
        ) as report_failure,
        pytest.raises(aiounifi.ServiceUnavailable),
    ):
        await hub.entity_loader._async_update_system_information()

    report_failure.assert_called_once()
    assert not hub.available


async def test_connection_failure_reports_are_deduplicated(
    caplog: pytest.LogCaptureFixture,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Ensure concurrent failure sources schedule only one retry."""
    connection = config_entry_setup.runtime_data.connection

    connection.report_failure()
    retry_handle = connection._retry_handle
    connection.report_failure()
    connection._set_available(True)
    connection._set_available(True)

    assert connection._retry_handle is retry_handle
    assert connection._attempt == 1
    assert caplog.text.count("Connection to UniFi Network lost") == 1
    assert caplog.text.count("Connection to UniFi Network restored") == 1


async def test_connection_does_not_retry_after_stop(
    config_entry_setup: MockConfigEntry,
) -> None:
    """Ensure late failures cannot schedule reconnect work after shutdown."""
    connection = config_entry_setup.runtime_data.connection

    connection.stop()
    connection.report_failure()

    assert connection.available
    assert connection._retry_handle is None
    assert connection._attempt == 0


async def test_failed_setup_cancels_connection_retry(
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Ensure a retry scheduled during a failed setup does not outlive the entry."""
    with (
        patch(
            "aiounifi.interfaces.system_information.SystemInformationHandler.update",
            side_effect=aiounifi.ServiceUnavailable,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            side_effect=RuntimeError,
        ),
    ):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.runtime_data.connection._retry_handle is None


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


@pytest.mark.parametrize(
    "exception",
    [aiounifi.ServiceUnavailable, aiounifi.Unauthorized, aiounifi.LoginRequired],
)
async def test_connection_waits_for_network_application_after_login(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """Keep the hub unavailable until the Network application answers."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()
    assert not hub.available

    with (
        patch.object(
            hub.api.system_information,
            "update",
            side_effect=exception,
        ),
        patch.object(config_entry_setup, "async_start_reauth") as start_reauth,
    ):
        await mock_websocket_state.reconnect()

    assert not hub.available
    assert hub.connection._attempt == 2
    start_reauth.assert_not_called()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=40))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hub.available
    assert hub.connection._attempt == 2

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=CONNECTION_STABLE_PERIOD + 30)
    )
    await hass.async_block_till_done()

    assert hub.connection._attempt == 0


async def test_backoff_grows_when_websocket_fails_after_login(
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Keep backing off while a successful login is followed by a failing transport."""
    connection = config_entry_setup.runtime_data.connection

    await mock_websocket_state.disconnect()
    assert connection._attempt == 1

    await mock_websocket_state.reconnect(fail=True)
    assert connection._attempt == 2

    await mock_websocket_state.reconnect(fail=True)
    assert connection._attempt == 3


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


@pytest.mark.parametrize(
    "exception",
    [
        aiounifi.LoginRequired,
        aiounifi.NoPermission,
        aiounifi.TwoFaTokenRequired,
        aiounifi.Unauthorized,
    ],
)
async def test_reconnect_auth_failure_starts_reauth(
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """Stop retrying and start reauthentication when login rejects credentials."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()

    with (
        patch.object(hub.api, "login", side_effect=exception),
        patch.object(config_entry_setup, "async_start_reauth") as start_reauth,
    ):
        await mock_websocket_state.reconnect()

    start_reauth.assert_called_once_with(hub.hass)
    assert hub.connection._reauth_required
    assert hub.connection._retry_handle is None


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


async def test_failure_during_slow_recovery_keeps_retrying(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Retry again when the application goes away while a resync is still running."""
    hub = config_entry_setup.runtime_data
    probe_calls = 0

    async def system_information_update() -> None:
        # The readiness probe passes, the check after the failed refetch does not
        nonlocal probe_calls
        probe_calls += 1
        if probe_calls == 2:
            raise aiounifi.RequestError

    async def slow_device_update() -> None:
        # The next retry falls due while this refetch is still in flight
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=45))
        await asyncio.sleep(0)

    await mock_websocket_state.disconnect()
    with (
        patch.object(
            hub.api.system_information, "update", side_effect=system_information_update
        ),
        patch.object(hub.api.clients, "update", side_effect=aiounifi.RequestError),
        patch.object(hub.api.devices, "update", side_effect=slow_device_update),
    ):
        await mock_websocket_state.reconnect()

    assert not hub.available

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hub.available


async def test_recovery_that_hangs_is_retried(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Give up on a resync that does not finish and try again."""
    hub = config_entry_setup.runtime_data

    async def hanging_update() -> None:
        await asyncio.Event().wait()

    await mock_websocket_state.disconnect()
    with patch.object(hub.api.devices, "update", side_effect=hanging_update):
        mock_websocket_state.clear()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
        await hass.async_block_till_done()
        assert hub.available

        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=RECOVERY_TIMEOUT + 1)
        )
        # block_till_done skips tasks that are being cancelled
        for _ in range(5):
            await asyncio.sleep(0)
        assert not hub.available

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hub.available


@pytest.mark.parametrize("client_payload", [[WIRELESS_CLIENT]])
@pytest.mark.parametrize(
    "exception", [aiounifi.ResponseError, aiounifi.Forbidden, aiounifi.NoPermission]
)
@pytest.mark.usefixtures("mock_device_registry")
async def test_rejected_resync_keeps_pushed_data(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """Keep websocket fed entities available when their refetch is rejected."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()

    with patch.object(hub.api.clients, "update", side_effect=exception):
        await mock_websocket_state.reconnect()

    assert hub.available
    assert hass.states.get("device_tracker.client_1").state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exception",
    [aiounifi.Forbidden, aiounifi.NoPermission, aiounifi.ResponseError],
)
async def test_rejected_readiness_probe_still_recovers(
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """An application that answers the probe with a rejection is ready."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()

    with patch.object(hub.api.system_information, "update", side_effect=exception):
        await mock_websocket_state.reconnect()

    assert hub.available


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ValueError, id="malformed_answer"),
        pytest.param(KeyError, id="unexpected_error"),
    ],
)
async def test_failed_readiness_probe_keeps_retrying(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """Retry after the readiness probe failed with a malformed answer."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()

    with patch.object(hub.api.system_information, "update", side_effect=exception):
        await mock_websocket_state.reconnect(fail=True)
    assert not hub.available

    await mock_websocket_state.reconnect()
    assert hub.available


async def test_no_polling_while_connection_is_down(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Send no data requests and log no errors while the session is down."""
    hub = config_entry_setup.runtime_data

    def data_requests() -> int:
        return sum(
            1
            for call in aioclient_mock.mock_calls
            if "/stat/sysinfo" not in str(call[1])
        )

    with patch.object(hub.api, "login", side_effect=aiounifi.RequestError):
        await mock_websocket_state.disconnect()
        requests = data_requests()

        async_fire_time_changed(hass, dt_util.utcnow() + IDLE_POLL_INTERVAL * 2)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert not hub.available
    assert data_requests() == requests
    assert not [
        record for record in caplog.records if record.levelno >= logging.WARNING
    ]


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


async def test_two_factor_prompt_from_readiness_probe_starts_reauth(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A session that now needs 2FA ends in reauthentication."""
    hub = config_entry_setup.runtime_data
    await mock_websocket_state.disconnect()

    with (
        patch.object(
            hub.api.system_information,
            "update",
            side_effect=aiounifi.TwoFaTokenRequired,
        ),
        patch.object(config_entry_setup, "async_start_reauth") as start_reauth,
    ):
        await mock_websocket_state.reconnect()
        assert not hub.available
        start_reauth.assert_not_called()

        with patch.object(hub.api, "login", side_effect=aiounifi.TwoFaTokenRequired):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
            await hass.async_block_till_done(wait_background_tasks=True)

    start_reauth.assert_called_once_with(hass)


async def test_polled_coordinator_quiet_while_connection_is_down(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pause polling during an outage and resume it after recovery."""
    hub = config_entry_setup.runtime_data
    coordinator = hub.entity_loader.get_data_update_coordinator(
        hub.api.object_oriented_network_configs
    )
    calls: list[None] = []
    coordinator.async_add_listener(lambda: calls.append(None))

    with patch.object(hub.api, "login", side_effect=aiounifi.RequestError):
        await mock_websocket_state.disconnect()
        calls.clear()
        async_fire_time_changed(hass, dt_util.utcnow() + IDLE_POLL_INTERVAL * 2)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert not calls
    assert coordinator.last_update_success
    assert "Fetching UniFi" not in caplog.text

    mock_websocket_state.clear()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hub.available
    assert calls

    calls.clear()
    async_fire_time_changed(hass, dt_util.utcnow() + IDLE_POLL_INTERVAL)
    await hass.async_block_till_done()
    assert calls
