"""Tests for the OpenWrt (ubus) integration setup."""

from datetime import timedelta
from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.const import DEFAULT_CONSIDER_HOME
from homeassistant.components.ubus.config_flow import HUB_TITLE
from homeassistant.components.ubus.const import DOMAIN, SUBENTRY_TYPE_ROUTER
from homeassistant.components.ubus.device_tracker import UbusScannerEntity
from homeassistant.config_entries import (
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_SSL,
    CONF_VERIFY_SSL,
    STATE_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .conftest import (
    MAC_LAPTOP,
    MAC_PHONE,
    MOCK_CONFIG,
    MOCK_HOST,
    MOCK_HOST_B,
    MOCK_HOST_CONFIG_B,
    router_subentry_data,
)


async def test_setup_creates_one_coordinator_per_subentry(
    hass: HomeAssistant,
    two_router_hub: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test one coordinator is created per router subentry."""
    two_router_hub.add_to_hass(hass)
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    assert two_router_hub.state is ConfigEntryState.LOADED
    assert set(two_router_hub.runtime_data) == set(two_router_hub.subentries)
    for subentry_id, coordinator in two_router_hub.runtime_data.items():
        assert coordinator.config_entry is two_router_hub
        assert coordinator.subentry is two_router_hub.subentries[subentry_id]


async def test_setup_entry_without_subentries(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test a hub without routers sets up without coordinators."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title=HUB_TITLE)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data == {}
    assert DOMAIN in hass.data


@pytest.mark.parametrize(
    ("method", "behavior"),
    [
        pytest.param("connect", {"side_effect": TypeError}, id="unreachable"),
        pytest.param("connect", {"side_effect": PermissionError}, id="access_denied"),
        pytest.param(
            "connect", {"side_effect": None, "return_value": None}, id="no_session"
        ),
        pytest.param(
            "get_hostapd_clients",
            {"side_effect": PermissionError},
            id="session_stays_denied",
        ),
    ],
)
async def test_first_refresh_failure_does_not_fail_setup(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
    method: str,
    behavior: dict[str, Any],
) -> None:
    """Test an unreadable router is marked unhealthy instead of failing setup."""
    getattr(mock_ubus.return_value, method).configure_mock(**behavior)

    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state is ConfigEntryState.LOADED
    shared = hass.data[DOMAIN]
    assert set(shared.health) == set(hub_entry.subentries)
    assert not any(shared.health.values())


async def test_persistent_invalid_credentials_issue(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test failing credentials open a repair issue, closed on recovery."""
    mock_ubus.return_value.connect.configure_mock(side_effect=None, return_value=None)
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    subentry_id = next(iter(hub_entry.subentries))
    assert any(
        issue.domain == DOMAIN
        and issue.translation_key == "persistent_invalid_credentials"
        and issue.config_subentry_id == subentry_id
        for issue in issue_registry.issues.values()
    )

    mock_ubus.return_value.connect.configure_mock(
        side_effect=None, return_value="session-id"
    )
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not any(
        issue.domain == DOMAIN
        and issue.translation_key == "persistent_invalid_credentials"
        for issue in issue_registry.issues.values()
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_subentry_added_triggers_reload(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test adding a router subentry reloads the hub and adds its coordinator."""
    _mock, ubus = mock_ubus_by_host
    hub_entry.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hub_entry.runtime_data) == 1

    hass.config_entries.async_add_subentry(
        hub_entry,
        ConfigSubentry(
            data=MappingProxyType(MOCK_HOST_CONFIG_B),
            subentry_type=SUBENTRY_TYPE_ROUTER,
            title=MOCK_HOST_B,
            unique_id=MOCK_HOST_B,
        ),
    )
    await hass.async_block_till_done()

    assert hub_entry.state is ConfigEntryState.LOADED
    assert len(hub_entry.runtime_data) == 2

    # The new router's clients are tracked.
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_LAPTOP: {"authorized": True}}
    }
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["source"] == MOCK_HOST_B


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_subentry_removed_releases_its_stamps(
    hass: HomeAssistant,
    two_router_hub: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing a router subentry releases its stamps and keeps its trackers."""
    _mock, ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    ubus[MOCK_HOST_B].get_hostapd_clients.return_value = {
        "clients": {MAC_LAPTOP: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(two_router_hub.entry_id)
    await hass.async_block_till_done()

    phone_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    laptop_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_LAPTOP
    )
    assert hass.states.get(phone_id).state == STATE_HOME
    assert hass.states.get(laptop_id).state == STATE_HOME

    subentry_b = next(
        subentry
        for subentry in two_router_hub.subentries.values()
        if subentry.data[CONF_HOST] == MOCK_HOST_B
    )
    hass.config_entries.async_remove_subentry(two_router_hub, subentry_b.subentry_id)
    await hass.async_block_till_done()

    # The entry stays loaded with its remaining router.
    assert two_router_hub.state is ConfigEntryState.LOADED
    assert len(two_router_hub.subentries) == 1
    assert len(two_router_hub.runtime_data) == 1

    # The trackers and devices stay registered to the hub; nothing moves.
    assert (
        entity_registry.async_get(laptop_id).config_entry_id == two_router_hub.entry_id
    )
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_LAPTOP), two_router_hub.entry_id
    )
    # The laptop's stamps were released with its router, so it is
    # unavailable, while the remaining router still reports the phone.
    assert hass.states.get(laptop_id).state == STATE_UNAVAILABLE
    assert hass.states.get(phone_id).state == STATE_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_disabling_entry_disables_trackers(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabling the hub disables all of its trackers."""
    _mock, ubus = mock_ubus_by_host
    hub_entry.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert entity_registry.async_get(entity_id).disabled_by is None

    await hass.config_entries.async_set_disabled_by(
        hub_entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert hub_entry.state is ConfigEntryState.NOT_LOADED
    assert (
        entity_registry.async_get(entity_id).disabled_by
        is er.RegistryEntryDisabler.CONFIG_ENTRY
    )


async def test_removing_last_entry_drops_shared_state(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test removing the last entry drops the shared state."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.data

    await hass.config_entries.async_remove(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN not in hass.data


@pytest.mark.parametrize(
    ("ssl", "verify_ssl"),
    [
        pytest.param(False, False, id="http"),
        pytest.param(True, False, id="https"),
        pytest.param(True, True, id="https_verified"),
    ],
)
async def test_ubus_client_construction(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    ssl: bool,
    verify_ssl: bool,
) -> None:
    """Test the ubus client uses the subentry's scheme and verification."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[
            router_subentry_data(
                {**MOCK_CONFIG, CONF_SSL: ssl, CONF_VERIFY_SSL: verify_ssl}
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_ubus.assert_called_once_with(
        f"{'https' if ssl else 'http'}://{MOCK_HOST}/ubus",
        "root",
        "password",
        verify=verify_ssl,
    )


async def test_ubus_client_defaults_without_ssl_options(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
) -> None:
    """Test a subentry without the SSL options defaults to HTTP and verification."""
    subentry = next(iter(hub_entry.subentries.values()))
    data = dict(subentry.data)
    del data[CONF_SSL]
    del data[CONF_VERIFY_SSL]
    hub_entry.add_to_hass(hass)
    hass.config_entries.async_update_subentry(hub_entry, subentry, data=data)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    mock_ubus.assert_called_once_with(
        f"http://{MOCK_HOST}/ubus", "root", "password", verify=True
    )


async def test_session_refreshed_after_permission_error(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a dropped session is re-authenticated and the scan retried."""
    mock_ubus.return_value.get_hostapd_clients.side_effect = [
        PermissionError,
        {
            "clients": {
                MAC_PHONE: {"authorized": True},
                MAC_LAPTOP: {"authorized": True},
            }
        },
    ]

    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state is ConfigEntryState.LOADED
    assert mock_ubus.return_value.connect.call_count == 2
    entries = er.async_entries_for_config_entry(entity_registry, hub_entry.entry_id)
    assert {e.unique_id for e in entries} == {MAC_PHONE, MAC_LAPTOP}


async def test_unload_entry(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
) -> None:
    """Test the config entry unloads cleanly."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert hub_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert hub_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "enabled", [pytest.param(False, id="disabled"), pytest.param(True, id="enabled")]
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
) -> None:
    """Test only a client which is not connected can be removed."""
    monkeypatch.setattr(
        UbusScannerEntity, "_attr_entity_registry_enabled_default", enabled
    )
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)
    connection = (dr.CONNECTION_NETWORK_MAC, MAC_PHONE)
    device_entry = device_registry.async_get_device_by_connection(
        connection, hub_entry.entry_id
    )
    assert device_entry is not None

    response = await ws_client.remove_device(device_entry.id)
    assert not response["success"]
    assert device_registry.async_get(device_entry.id)

    clients = mock_ubus.return_value.get_hostapd_clients
    connected = clients.return_value
    clients.return_value = {"clients": {MAC_LAPTOP: {"authorized": True}}}
    # The client stays connected for CONSIDER_HOME after its last stamp,
    # so it can only be removed once that stamp has aged out.
    freezer.tick(DEFAULT_CONSIDER_HOME + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    response = await ws_client.remove_device(device_entry.id)
    assert response["success"]
    assert not device_registry.async_get(device_entry.id)
    assert not entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC_PHONE)

    # A removed client is tracked again when it reconnects.
    clients.return_value = connected
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get_device_by_connection(
        connection, hub_entry.entry_id
    )
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC_PHONE)
    assert entity_id is not None
    assert (hass.states.get(entity_id) is not None) is enabled


async def test_remove_config_entry_device_rejects_child_device(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing an unexpected child device is rejected."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    parent_device = device_registry.async_get_or_create(
        config_entry_id=hub_entry.entry_id,
        identifiers={(DOMAIN, "parent")},
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=hub_entry.entry_id,
        identifiers={(DOMAIN, "child")},
        parent_device_id=parent_device.id,
    )
    ws_client = await hass_ws_client(hass)

    response = await ws_client.remove_device(child_device.id)

    assert not response["success"]
    assert device_registry.async_get(child_device.id)


async def test_remove_device_of_unloaded_entry(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a client device can be removed while the entry is not loaded."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), hub_entry.entry_id
    )
    assert device_entry is not None
    ws_client = await hass_ws_client(hass)

    response = await ws_client.remove_device(device_entry.id)

    assert response["success"]
    assert not device_registry.async_get(device_entry.id)
