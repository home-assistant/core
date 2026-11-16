"""Test UniFi Network."""

import asyncio
from datetime import timedelta
import logging
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

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
)
from homeassistant.components.unifi.errors import (
    AuthenticationRequired,
    CannotConnect,
    MfaRequired,
)
from homeassistant.components.unifi.hub import get_unifi_api
from homeassistant.components.unifi.hub.connection import REQUEST_TIMEOUT
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import EVENT_STATE_REPORTED, Platform
from homeassistant.core import Event, EventStateReportedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import (
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
    invalid_json,
)

SITES_UPDATE = "aiounifi.interfaces.sites.Sites.update"
SYSTEM_INFORMATION_UPDATE = (
    "aiounifi.interfaces.system_information.SystemInformationHandler.update"
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
        pytest.param(SYSTEM_INFORMATION_UPDATE, invalid_json(), id="invalid_json"),
        pytest.param(
            SYSTEM_INFORMATION_UPDATE,
            aiounifi.AuthenticationRateLimitError,
            id="rate_limited",
        ),
        pytest.param(SYSTEM_INFORMATION_UPDATE, aiounifi.Forbidden, id="forbidden"),
        pytest.param(
            SYSTEM_INFORMATION_UPDATE, aiounifi.NoPermission, id="no_permission"
        ),
        pytest.param(
            SYSTEM_INFORMATION_UPDATE, aiounifi.Unauthorized, id="unauthorized"
        ),
        pytest.param(SITES_UPDATE, aiounifi.ServiceUnavailable, id="no_site_list"),
        pytest.param(SITES_UPDATE, invalid_json(), id="invalid_site_list"),
        pytest.param(SITES_UPDATE, aiounifi.Forbidden, id="site_list_rejected"),
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


@pytest.mark.parametrize(
    "target",
    [
        pytest.param(SITES_UPDATE, id="sites"),
        pytest.param(SYSTEM_INFORMATION_UPDATE, id="system_information"),
    ],
)
async def test_setup_asks_for_reauth_when_account_needs_mfa(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    target: str,
) -> None:
    """Only the user can resolve multi-factor authentication."""
    with patch(target, side_effect=aiounifi.TwoFaTokenRequired):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_setup_continues_when_system_information_answers_an_error(
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """An application that answers with an error is up."""
    with patch(SYSTEM_INFORMATION_UPDATE, side_effect=aiounifi.ResponseError):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.LOADED


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
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=timeout + 1))
        config_entry = await setup

    assert config_entry.state is state


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


@pytest.mark.parametrize(
    "site_payload",
    [
        pytest.param(site("site_id", NEW_SITE_ID), id="one_site"),
        pytest.param(
            [
                *site("other", "1b2c3d4e-5f6a-4b7c-8d9e-0f1a2b3c4d5e"),
                *site("site_id", NEW_SITE_ID),
            ],
            id="several_sites",
        ),
    ],
)
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
    assert config_entry.reason == "The configured UniFi Network site no longer exists"
    assert config_entry.unique_id == unique_id


@pytest.mark.parametrize(
    ("side_effect", "raised_exception"),
    [
        (TimeoutError, CannotConnect),
        (aiounifi.BadGateway, CannotConnect),
        (aiounifi.Forbidden, CannotConnect),
        (aiounifi.ServiceUnavailable, CannotConnect),
        (aiounifi.RequestError, CannotConnect),
        (aiounifi.ResponseError, CannotConnect),
        (aiounifi.AuthenticationRateLimitError, CannotConnect),
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


async def test_get_unifi_api_mfa_required(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry_data: MappingProxyType[str, Any],
) -> None:
    """Check that a login requiring MFA is reported as such without a traceback."""
    with (
        patch("aiounifi.Controller.login", side_effect=aiounifi.TwoFaTokenRequired),
        pytest.raises(MfaRequired),
    ):
        await get_unifi_api(hass, config_entry_data)
    (record,) = [r for r in caplog.records if r.name.startswith("homeassistant")]
    assert record.levelno == logging.WARNING
    assert record.exc_info is None
    assert "requires multi-factor authentication" in record.getMessage()
