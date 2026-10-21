"""Test UniFi Network."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterator
from contextlib import contextmanager
from datetime import timedelta
from http import HTTPStatus
import json
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
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.unifi.const import CONF_BLOCK_CLIENT, DOMAIN
from homeassistant.components.unifi.coordinator import (
    IDLE_POLL_INTERVAL,
    POLL_INTERVAL,
    UPDATE_TIMEOUT,
    UnifiDataUpdateCoordinator,
)
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.components.unifi.hub import UnifiHub, get_unifi_api
from homeassistant.components.unifi.hub.connection import (
    CONNECTION_STABLE_PERIOD,
    RATE_LIMIT_PAUSE,
    REAUTH_RETRY_INTERVAL,
    RECOVERY_TIMEOUT,
    REQUEST_TIMEOUT,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_REPORTED,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import Event, EventStateReportedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from .conftest import (
    FIRST_RETRY_DELAY,
    MAX_RETRY_DELAY,
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
    retry_window,
)

SITES_UPDATE = "aiounifi.interfaces.sites.Sites.update"
SYSTEM_INFORMATION_UPDATE = (
    "aiounifi.interfaces.system_information.SystemInformationHandler.update"
)

# What aiounifi raises for a body that is not JSON
INVALID_JSON = json.JSONDecodeError("Expecting value", "", 0)

WIRELESS_CLIENT = {
    "ap_mac": "00:00:00:00:02:01",
    "essid": "ssid",
    "hostname": "client_1",
    "ip": "10.0.0.1",
    "is_wired": False,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:01",
}


def _fire(hass: HomeAssistant, seconds: float) -> None:
    """Fire timers due within the given number of seconds, without waiting."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))


async def _advance(hass: HomeAssistant, seconds: float) -> None:
    """Fire timers due within the given number of seconds and wait for them."""
    _fire(hass, seconds)
    await hass.async_block_till_done(wait_background_tasks=True)


def _availability_reached(
    hass: HomeAssistant, entry: MockConfigEntry, available: bool
) -> asyncio.Event:
    """Return an event set once the hub reports the given availability."""
    hub = entry.runtime_data
    reached = asyncio.Event()

    @callback
    def _changed() -> None:
        if hub.available is available:
            reached.set()

    entry.async_on_unload(
        async_dispatcher_connect(hass, hub.signal_reachable, _changed)
    )
    return reached


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
        async_fire_time_changed(hass, dt_util.utcnow() + IDLE_POLL_INTERVAL)
        await hass.async_block_till_done(wait_background_tasks=True)

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
        async_fire_time_changed(hass, dt_util.utcnow() + IDLE_POLL_INTERVAL)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert coordinator.update_interval is None
        assert coordinator.last_update_success is False
        assert mock_update.call_count == 1

        async_fire_time_changed(hass, dt_util.utcnow() + POLL_INTERVAL)
        await hass.async_block_till_done()

        assert mock_update.call_count == 1

        # pylint: disable-next=home-assistant-tests-coordinator-async-refresh
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
        async_fire_time_changed(hass, dt_util.utcnow() + POLL_INTERVAL)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.last_update_success is False
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"

    async_fire_time_changed(hass, dt_util.utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.last_update_success is True
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"


@pytest.mark.parametrize(
    ("target", "exception"),
    [
        pytest.param(
            SYSTEM_INFORMATION_UPDATE, aiounifi.ServiceUnavailable, id="starting"
        ),
        pytest.param(SYSTEM_INFORMATION_UPDATE, TimeoutError, id="timeout"),
        pytest.param(
            SYSTEM_INFORMATION_UPDATE, aiounifi.LoginRequired, id="login_required"
        ),
        pytest.param(SYSTEM_INFORMATION_UPDATE, INVALID_JSON, id="invalid_json"),
        pytest.param(SITES_UPDATE, aiounifi.ServiceUnavailable, id="no_site_list"),
        # Without a side effect the patched update leaves the site list empty
        pytest.param(SITES_UPDATE, None, id="no_sites_yet"),
    ],
)
async def test_setup_retries_when_network_application_not_ready(
    config_entry_factory: ConfigEntryFactoryType,
    target: str,
    exception: type[Exception] | None,
) -> None:
    """Retry setup while the Network application cannot answer yet."""
    with patch(target, side_effect=exception):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("exception", [aiounifi.Forbidden, aiounifi.NoPermission])
async def test_setup_continues_when_system_information_is_rejected(
    config_entry_factory: ConfigEntryFactoryType,
    exception: type[Exception],
) -> None:
    """An application that rejects system information is up."""
    with patch(SYSTEM_INFORMATION_UPDATE, side_effect=exception):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.available


@pytest.mark.parametrize(
    ("target", "timeout", "state"),
    [
        pytest.param(
            SITES_UPDATE,
            REQUEST_TIMEOUT,
            ConfigEntryState.SETUP_RETRY,
            id="sites",
        ),
        pytest.param(
            SYSTEM_INFORMATION_UPDATE,
            REQUEST_TIMEOUT,
            ConfigEntryState.SETUP_RETRY,
            id="system_information",
        ),
        pytest.param(
            "aiounifi.interfaces.clients_all.ClientsAll.update",
            UPDATE_TIMEOUT,
            ConfigEntryState.LOADED,
            id="inactive_clients",
        ),
    ],
)
async def test_setup_gives_up_on_hanging_request(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    target: str,
    timeout: int,
    state: ConfigEntryState,
) -> None:
    """Setup does not wait forever for a request that never answers."""
    started = asyncio.Event()

    async def hang(*args: object) -> None:
        started.set()
        await asyncio.Event().wait()

    with patch(target, side_effect=hang):
        setup = hass.async_create_task(config_entry_factory())
        await started.wait()
        _fire(hass, timeout + 1)
        config_entry = await setup

    assert config_entry.state is state


async def test_connection_recovery_does_not_restart_running_websocket(
    hass: HomeAssistant,
    hub: UnifiHub,
    polled_coordinator: UnifiDataUpdateCoordinator,
) -> None:
    """Ensure recovery keeps an active websocket instead of starting another."""
    with (
        patch.object(
            polled_coordinator.handler, "update", side_effect=aiounifi.RequestError
        ),
        patch.object(
            hub.api.system_information, "update", side_effect=aiounifi.RequestError
        ),
    ):
        await _advance(hass, IDLE_POLL_INTERVAL.total_seconds())
    assert not hub.available

    with patch.object(hub.api, "start_websocket") as start_websocket:
        await _advance(hass, MAX_RETRY_DELAY)

    assert hub.available
    start_websocket.assert_not_called()


@pytest.mark.parametrize(
    "request_suffix",
    ["/stat/sta", "/stat/device", "/trafficrules", "/rest/wlanconf"],
)
async def test_recovery_refetches_each_handler_once(
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    request_suffix: str,
) -> None:
    """Refetch every handler exactly once after the connection is restored."""

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


OLD_SITE_ID = "5f0a1b2c3d4e5f6a7b8c9d0e"
NEW_SITE_ID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"


def site(name: str, site_id: str) -> list[dict[str, Any]]:
    """Return a site payload."""
    return [{"desc": "Site name", "name": name, "role": "admin", "_id": site_id}]


@pytest.mark.parametrize("site_payload", [site("site_id", NEW_SITE_ID)])
async def test_site_id_changed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Follow a site from its ObjectId to the UUID UniFi Network 11 gives it."""
    hass.config_entries.async_update_entry(config_entry, unique_id=OLD_SITE_ID)
    devices = {
        domain: device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id, identifiers={(domain, OLD_SITE_ID)}
        )
        for domain in (DOMAIN, SWITCH_DOMAIN)
    }

    await config_entry_factory()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.unique_id == NEW_SITE_ID
    for domain, device in devices.items():
        assert device_registry.async_get_device_by_identifier(
            (domain, NEW_SITE_ID), config_entry.entry_id
        ) == device_registry.async_get(device.id)


@pytest.mark.parametrize(
    ("unique_id", "site_payload", "other_entry_unique_id"),
    [
        pytest.param(
            OLD_SITE_ID,
            site("other", NEW_SITE_ID),
            "2",
            id="no_site_with_configured_name",
        ),
        pytest.param(
            OLD_SITE_ID,
            site("site_id", NEW_SITE_ID),
            NEW_SITE_ID,
            id="new_id_already_configured",
        ),
        pytest.param(
            "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
            site("site_id", NEW_SITE_ID),
            "2",
            id="old_id_not_object_id",
        ),
        pytest.param(
            OLD_SITE_ID,
            site("site_id", "6f0a1b2c3d4e5f6a7b8c9d0e"),
            "2",
            id="new_id_not_uuid",
        ),
    ],
)
async def test_site_id_changed_not_followed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
    unique_id: str,
    other_entry_unique_id: str,
) -> None:
    """Keep the entry untouched unless it is the ObjectId to UUID site change."""
    hass.config_entries.async_update_entry(config_entry, unique_id=unique_id)
    MockConfigEntry(domain=DOMAIN, unique_id=other_entry_unique_id).add_to_hass(hass)

    # Requests for a site that is gone get 401, which must not retry the setup
    with patch(
        SYSTEM_INFORMATION_UPDATE,
        side_effect=aiounifi.LoginRequired,
    ):
        await config_entry_factory()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == f"UniFi site {unique_id} no longer exists"
    assert config_entry.unique_id == unique_id


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
        assert config_entry_setup.reason == "Failed to unload UniFi Network"


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

    # The session outlived the outage, so no login is needed
    with patch("aiounifi.Controller.login") as login:
        await mock_websocket_state.reconnect()
    login.assert_not_called()
    # Controller is once again connected
    assert hass.states.get("device_tracker.client").state == "home"


async def test_reconnect_mechanism(
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Verify a reconnect logs in again once the session expired."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234/",
        status=HTTPStatus.BAD_GATEWAY,
    )

    with patch.object(
        config_entry_setup.runtime_data.api.system_information,
        "update",
        side_effect=aiounifi.LoginRequired,
    ):
        await mock_websocket_state.disconnect()
        assert aioclient_mock.call_count == 0

        await mock_websocket_state.reconnect(fail=True)
        assert aioclient_mock.call_count == 1

        await mock_websocket_state.reconnect(fail=True)
        assert aioclient_mock.call_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(aiounifi.BadGateway, id="bad_gateway"),
        pytest.param(aiounifi.ServiceUnavailable, id="service_unavailable"),
        pytest.param(aiounifi.AiounifiException, id="unknown_error"),
    ],
)
async def test_reconnect_mechanism_exceptions(
    caplog: pytest.LogCaptureFixture,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    exception: type[Exception],
) -> None:
    """Keep retrying quietly after login errors that are not about credentials."""
    await mock_websocket_state.disconnect()

    with _expired_session(hub, AsyncMock(side_effect=exception)) as login:
        await mock_websocket_state.reconnect(fail=True)
    login.assert_called_once()
    assert not hub.available
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

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


async def test_unexpected_login_error_logs_one_traceback_per_outage(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A login that keeps failing unexpectedly does not flood the log."""

    def errors() -> int:
        return len([r for r in caplog.records if r.levelno >= logging.ERROR])

    with _expired_session(hub, AsyncMock(side_effect=KeyError)) as login:
        await mock_websocket_state.disconnect()
        for _ in range(3):
            await _advance(hass, MAX_RETRY_DELAY)
    assert login.call_count == 3
    assert errors() == 1

    mock_websocket_state.clear()
    with _expired_session(hub):
        await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available

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
    assert hub.available

    # A connection that drops again before it was stable keeps backing off
    with _expired_session(hub, AsyncMock(side_effect=aiounifi.RequestError)) as login:
        await mock_websocket_state.disconnect()
        await _advance(hass, FIRST_RETRY_DELAY)
    login.assert_not_called()

    mock_websocket_state.clear()
    with _expired_session(hub):
        await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available

    # Only a connection that stayed up starts the backoff over
    await _advance(hass, CONNECTION_STABLE_PERIOD)
    with _expired_session(hub, AsyncMock(side_effect=aiounifi.RequestError)) as login:
        await mock_websocket_state.disconnect()
        await _advance(hass, FIRST_RETRY_DELAY)
    login.assert_called_once()


async def test_concurrent_failures_check_session_and_log_in_once(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Endpoints and the websocket failing together share one check and login."""
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
        await probe_started.wait()
        await hass.async_block_till_done()
        # The websocket drops too while the session check runs
        mock_websocket_state.set()
        await hass.async_block_till_done()
        probe_release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        probe.assert_called_once()

        await _advance(hass, FIRST_RETRY_DELAY)

    login.assert_called_once()
    assert caplog.text.count("Connection to UniFi Network at 1.2.3.4 lost") == 1


@pytest.mark.parametrize(
    "stop",
    [
        pytest.param(_unload, id="unload"),
        pytest.param(_fire_stop, id="homeassistant_stop"),
    ],
)
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


@pytest.mark.parametrize(
    "stop",
    [
        pytest.param(_unload, id="unload"),
        pytest.param(_fire_stop, id="homeassistant_stop"),
    ],
)
async def test_login_in_flight_at_stop_does_not_retry(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    stop: Callable[[HomeAssistant, MockConfigEntry], Awaitable[None]],
) -> None:
    """Stopping during a login attempt schedules no further attempt."""
    hub = config_entry_setup.runtime_data
    login_started = asyncio.Event()

    with _expired_session(
        hub, AsyncMock(side_effect=_hang_first_call(login_started))
    ) as login:
        await mock_websocket_state.disconnect()
        _fire(hass, FIRST_RETRY_DELAY)
        await login_started.wait()

        await stop(hass, config_entry_setup)
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
        pytest.param(aiounifi.NoPermission, 1, id="no_permission"),
        pytest.param(aiounifi.TwoFaTokenRequired, 1, id="two_factor"),
        # A booting console can reject a login for a moment
        pytest.param(aiounifi.Unauthorized, 3, id="unauthorized"),
        pytest.param(aiounifi.Forbidden, 3, id="forbidden"),
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
        assert list(config_entry_setup.async_get_active_flows(hass, {SOURCE_REAUTH}))

        await _advance(hass, REAUTH_RETRY_INTERVAL)
        assert login.call_count == logins + 1

        # An unexpected error keeps the slow pace
        login.side_effect = KeyError
        await _advance(hass, REAUTH_RETRY_INTERVAL)
        await _advance(hass, MAX_RETRY_DELAY)
        assert login.call_count == logins + 2
        assert not hub.available

        login.side_effect = None
        mock_websocket_state.clear()
        await _advance(hass, REAUTH_RETRY_INTERVAL)

    assert hub.available
    assert not list(config_entry_setup.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    "logins",
    [
        # UniFi OS answers a login with 401 while its login service is down
        pytest.param([*[aiounifi.LoginRequired()] * 5, None], id="login_service_down"),
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
    ],
)
async def test_login_failures_that_do_not_start_reauth(
    hass: HomeAssistant,
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

    assert hub.available
    assert not list(config_entry_setup.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_briefly_rejected_login_recovers_without_reauth(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A console that rejects logins while booting recovers on its own."""
    hub = config_entry_setup.runtime_data
    login = AsyncMock(
        side_effect=[aiounifi.Unauthorized(), aiounifi.Unauthorized(), None]
    )

    with _expired_session(hub, login):
        await mock_websocket_state.disconnect()
        mock_websocket_state.clear()
        for _ in range(3):
            await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available

    # The rejections before the working login are forgotten
    await _advance(hass, CONNECTION_STABLE_PERIOD)
    with _expired_session(hub, AsyncMock(side_effect=aiounifi.Unauthorized)):
        await mock_websocket_state.disconnect()
        await _advance(hass, MAX_RETRY_DELAY)

    assert not list(config_entry_setup.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    ("exception", "ready"),
    [
        pytest.param(aiounifi.ServiceUnavailable, False, id="starting"),
        pytest.param(aiounifi.RequestError, False, id="unreachable"),
        pytest.param(TimeoutError, False, id="timeout"),
        pytest.param(aiounifi.LoginRequired, False, id="session_expired"),
        pytest.param(aiounifi.Unauthorized, False, id="unauthorized"),
        pytest.param(aiounifi.TwoFaTokenRequired, False, id="two_factor"),
        pytest.param(INVALID_JSON, False, id="invalid_json"),
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

    with _expired_session(hub, probe=AsyncMock(side_effect=exception)):
        await mock_websocket_state.disconnect()
        mock_websocket_state.clear()
        await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available is ready

    await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available
    assert not list(config_entry_setup.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_slow_readiness_probe_restores_session(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A busy Network application that answers slowly is not down."""
    probe_started = asyncio.Event()

    async def slow_probe() -> None:
        probe_started.set()
        await asyncio.sleep(7)

    await mock_websocket_state.disconnect()
    mock_websocket_state.clear()
    with patch.object(hub.api.system_information, "update", side_effect=slow_probe):
        _fire(hass, FIRST_RETRY_DELAY)
        await probe_started.wait()
        await _advance(hass, 8)

    assert hub.available


@pytest.mark.parametrize(
    "poll_error",
    [
        pytest.param(aiounifi.RequestError, id="request_error"),
        pytest.param(aiounifi.LoginRequired, id="login_required"),
        pytest.param(aiounifi.BadGateway, id="bad_gateway"),
        pytest.param(aiounifi.ServiceUnavailable, id="service_unavailable"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(INVALID_JSON, id="invalid_json"),
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
    ):
        await _advance(hass, IDLE_POLL_INTERVAL.total_seconds())

    assert hub.available is available
    assert not polled_coordinator.last_update_success


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
    assert hub.available
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
        await went_down.wait()

    with (
        _expired_session(hub, AsyncMock(side_effect=aiounifi.RequestError)),
        patch.object(
            polled_coordinator.handler,
            "update",
            side_effect=update_while_connection_drops,
        ) as update,
    ):
        await _advance(hass, IDLE_POLL_INTERVAL.total_seconds())
        assert not hub.available
        requests = aioclient_mock.call_count
        calls.clear()
        await _advance(hass, (IDLE_POLL_INTERVAL * 2).total_seconds())

    update.assert_called_once()
    assert aioclient_mock.call_count == requests
    assert not calls
    assert polled_coordinator.last_update_success
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


@contextmanager
def _recovery_loses_session(
    hub: UnifiHub, login: AsyncMock | None = None
) -> Iterator[tuple[AsyncMock, AsyncMock]]:
    """Log in fine, then lose the session again while the clients are refetched."""
    # The readiness probe passes, the checks after the failed refetch do not
    probe = AsyncMock(side_effect=[None, *[aiounifi.RequestError()] * 10])
    with (
        _expired_session(hub, login, probe) as login_mock,
        patch.object(hub.api.clients, "update", side_effect=aiounifi.RequestError),
    ):
        yield login_mock, probe


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
        await resync_started.wait()
        await went_down.wait()

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
    assert hub.available
    login.assert_called_once()


async def test_backoff_keeps_growing_when_recovery_loses_session(
    hass: HomeAssistant,
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """A recovery that drops during resync does not start the backoff over."""
    await mock_websocket_state.disconnect()
    with _recovery_loses_session(
        hub, AsyncMock(side_effect=[None, *[aiounifi.RequestError()] * 5])
    ) as (login, _):
        await _advance(hass, FIRST_RETRY_DELAY)
        assert not hub.available
        # Logins two and three fail, the next delay is already capped
        await _advance(hass, MAX_RETRY_DELAY)
        await _advance(hass, MAX_RETRY_DELAY)
        assert login.call_count == 3
        await _advance(hass, FIRST_RETRY_DELAY)

    assert login.call_count == 3


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
        await resync_started.wait()
        assert hub.available

        # The timeout cancels the attempt, block_till_done skips cancelling tasks
        went_down = _availability_reached(hass, config_entry_setup, False)
        _fire(hass, RECOVERY_TIMEOUT + 1)
        await went_down.wait()
        assert not hub.available

    await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(INVALID_JSON, id="invalid_json"),
        pytest.param(aiounifi.RequestError, id="request_error"),
        pytest.param(aiounifi.ResponseError, id="response_error"),
        pytest.param(aiounifi.Forbidden, id="forbidden"),
        pytest.param(aiounifi.NoPermission, id="no_permission"),
        pytest.param(KeyError, id="unexpected_error"),
    ],
)
@pytest.mark.parametrize("client_payload", [[WIRELESS_CLIENT]])
@pytest.mark.usefixtures("mock_device_registry")
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
    hub: UnifiHub,
    mock_websocket_state: WebsocketStateManager,
    exception: Exception,
) -> None:
    """A websocket that fails after recovery takes the session down again."""
    await mock_websocket_state.disconnect()
    with patch.object(hub.api, "start_websocket", side_effect=exception):
        await _advance(hass, MAX_RETRY_DELAY)

    assert not hub.available


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
        await resync_started.wait()

        # The handler gives up before the whole recovery would
        _fire(hass, UPDATE_TIMEOUT + 1)
        await websocket_started.wait()

    assert hub.available


async def test_poll_hanging_from_before_outage_does_not_delay_recovery(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    polled_coordinator: UnifiDataUpdateCoordinator,
) -> None:
    """Resume push updates without waiting for a poll that started earlier."""
    hub = config_entry_setup.runtime_data
    poll_started = asyncio.Event()
    poll_release = asyncio.Event()
    websocket_started = asyncio.Event()

    async def hanging_poll() -> None:
        poll_started.set()
        await poll_release.wait()

    async def start_websocket() -> None:
        websocket_started.set()
        await asyncio.Event().wait()

    with (
        patch.object(polled_coordinator.handler, "update", side_effect=hanging_poll),
        patch.object(hub.api, "start_websocket", side_effect=start_websocket),
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await poll_started.wait()

        # The hanging poll is a background task, so don't wait for those
        went_down = _availability_reached(hass, config_entry_setup, False)
        mock_websocket_state.set()
        await went_down.wait()
        _fire(hass, FIRST_RETRY_DELAY)
        await websocket_started.wait()
        assert hub.available

        poll_release.set()
        await hass.async_block_till_done()


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


async def test_hanging_poll_times_out_and_checks_session(
    hass: HomeAssistant,
    hub: UnifiHub,
    polled_coordinator: UnifiDataUpdateCoordinator,
) -> None:
    """A poll that never answers fails and checks the session."""
    poll_started = asyncio.Event()
    probe_called = asyncio.Event()

    async def hanging_update() -> None:
        poll_started.set()
        await asyncio.Event().wait()

    async def probe() -> None:
        probe_called.set()

    with (
        patch.object(polled_coordinator.handler, "update", side_effect=hanging_update),
        patch.object(hub.api.system_information, "update", side_effect=probe),
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await poll_started.wait()
        _fire(hass, UPDATE_TIMEOUT + 1)
        await probe_called.wait()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hub.available
    assert not polled_coordinator.last_update_success


@pytest.mark.parametrize("step", ["login", "probe"])
async def test_hanging_reconnect_step_is_given_up_and_retried(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    step: str,
) -> None:
    """A login or probe that never answers does not block reconnecting forever."""
    started = asyncio.Event()
    hanging = {step: AsyncMock(side_effect=_hang_first_call(started))}

    with _expired_session(config_entry_setup.runtime_data, **hanging) as login:
        await mock_websocket_state.disconnect()
        _fire(hass, FIRST_RETRY_DELAY)
        await started.wait()

        _fire(hass, REQUEST_TIMEOUT + 1)
        await hass.async_block_till_done()
        # Background tasks are not awaited, the hanging attempt may never end
        _fire(hass, MAX_RETRY_DELAY)
        await hass.async_block_till_done()

    assert login.call_count == 2


async def test_hanging_session_check_marks_session_down(
    hass: HomeAssistant,
    hub: UnifiHub,
) -> None:
    """A session check that never answers counts as a lost session."""
    probe_started = asyncio.Event()

    with (
        patch.object(
            hub.api.traffic_rules, "update", side_effect=aiounifi.RequestError
        ),
        patch.object(
            hub.api.system_information,
            "update",
            side_effect=_hang_first_call(probe_started),
        ),
        patch.object(hub.api, "login", side_effect=aiounifi.RequestError),
    ):
        _fire(hass, IDLE_POLL_INTERVAL.total_seconds())
        await probe_started.wait()
        _fire(hass, REQUEST_TIMEOUT + 1)
        await hass.async_block_till_done()

    assert not hub.available


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

    with _expired_session(hub, login):
        await mock_websocket_state.disconnect()
        await _advance(hass, FIRST_RETRY_DELAY)
        assert login.call_count == 1
        await _advance(hass, RATE_LIMIT_PAUSE - 1)
        assert login.call_count == 1
        await _advance(hass, RATE_LIMIT_PAUSE)
        assert login.call_count == 2
        # The pause was for the limit only, retries back off as usual again
        await _advance(hass, MAX_RETRY_DELAY)
        assert login.call_count == 3
    assert "limits logins, pausing reconnects for 300 seconds" in caplog.text

    mock_websocket_state.clear()
    with _expired_session(hub):
        await _advance(hass, MAX_RETRY_DELAY)
    assert hub.available
    assert not list(config_entry_setup.async_get_active_flows(hass, {SOURCE_REAUTH}))
