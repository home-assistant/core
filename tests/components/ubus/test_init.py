"""Tests for the OpenWrt (ubus) integration setup."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.ubus.const import DOMAIN
from homeassistant.components.ubus.device_tracker import UbusScannerEntity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MAC_LAPTOP, MAC_PHONE


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
async def test_setup_retry(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    behavior: dict[str, Any],
) -> None:
    """Test the config entry retries setup when the router can't be read."""
    getattr(mock_ubus.return_value, method).configure_mock(**behavior)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_session_refreshed_after_permission_error(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
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

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_ubus.return_value.connect.call_count == 2
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {e.unique_id for e in entries} == {MAC_PHONE, MAC_LAPTOP}


async def test_unload_entry(
    hass: HomeAssistant, mock_ubus: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "enabled", [pytest.param(False, id="disabled"), pytest.param(True, id="enabled")]
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
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
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)
    connection = (dr.CONNECTION_NETWORK_MAC, MAC_PHONE)
    device_entry = device_registry.async_get_device_by_connection(
        connection, mock_config_entry.entry_id
    )
    assert device_entry is not None

    response = await ws_client.remove_device(device_entry.id)
    assert not response["success"]
    assert device_registry.async_get(device_entry.id)

    clients = mock_ubus.return_value.get_hostapd_clients
    connected = clients.return_value
    clients.return_value = {"clients": {MAC_LAPTOP: {"authorized": True}}}
    freezer.tick(timedelta(seconds=30))
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
        connection, mock_config_entry.entry_id
    )
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC_PHONE)
    assert entity_id is not None
    assert (hass.states.get(entity_id) is not None) is enabled


async def test_remove_config_entry_device_rejects_child_device(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing an unexpected child device is rejected."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    parent_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "parent")},
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
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
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a client device can be removed while the entry is not loaded."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "config", {})
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC_PHONE), mock_config_entry.entry_id
    )
    assert device_entry is not None
    ws_client = await hass_ws_client(hass)

    response = await ws_client.remove_device(device_entry.id)

    assert response["success"]
    assert not device_registry.async_get(device_entry.id)
