"""Tests for TP-Link Omada device tracker entities."""

from collections.abc import AsyncIterable
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
)
from syrupy.assertion import SnapshotAssertion
from tplink_omada_client.clients import OmadaConnectedClient
from tplink_omada_client.devices import OmadaListDevice

from homeassistant.components.tplink_omada.const import (
    CONF_SHOW_ONLY_ADOPTED_DEVICES,
    DOMAIN,
)
from homeassistant.components.tplink_omada.coordinator import POLL_CLIENTS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

UPDATE_INTERVAL = timedelta(seconds=10)
POLL_INTERVAL = timedelta(seconds=POLL_CLIENTS + 10)

MOCK_ENTRY_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "site": "SiteId",
    "username": "test-username",
    "password": "test-password",
}


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
) -> MockConfigEntry:
    """Set up the TP-Link Omada integration for testing."""
    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345",
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


async def test_device_scanner_created(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test gateway connected switches."""

    entity_id = "device_tracker.banana"

    updated_entity = entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert not updated_entity.disabled
    device = device_registry.async_get(updated_entity.device_id)
    assert device is not None
    assert device.name == "Banana"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "2c:71:ff:ed:34:83")}
    async_fire_time_changed(hass, utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity == snapshot


@pytest.mark.parametrize(
    ("identifier_domain", "has_disabled_entity", "device_retained"),
    [
        pytest.param("esphome", False, False, id="client-only"),
        pytest.param(DOMAIN, False, True, id="omada-identifier"),
        pytest.param("esphome", True, True, id="disabled-entity"),
    ],
)
async def test_adopted_devices_only_detaches_client_tracker(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_omada_clients_only_site_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    identifier_domain: str,
    has_disabled_entity: bool,
    device_retained: bool,
) -> None:
    """Keep the tracker settings while removing its client device."""
    entity_id = "device_tracker.banana"
    tracker = entity_registry.async_get(entity_id)
    assert tracker is not None
    device_id = tracker.device_id
    assert device_id is not None
    identifier = "shared-hardware"
    if identifier_domain == DOMAIN:
        devices = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
        ap = OmadaListDevice({**devices[0], "type": "ap"})
        identifier = ap.mac
        mock_omada_clients_only_site_client.get_devices.return_value = [ap]
    device_registry.async_update_device(
        device_id, new_identifiers={(identifier_domain, identifier)}
    )
    if has_disabled_entity:
        entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "other_entity",
            config_entry=init_integration,
            device_id=device_id,
            disabled_by=er.RegistryEntryDisabler.USER,
        )

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SHOW_ONLY_ADOPTED_DEVICES: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    tracker = entity_registry.async_get(entity_id)
    assert tracker is not None
    assert tracker.device_id is None
    assert (device_registry.async_get(device_id) is not None) is device_retained

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SHOW_ONLY_ADOPTED_DEVICES: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    restored_tracker = entity_registry.async_get(entity_id)
    assert restored_tracker is not None
    assert restored_tracker.device_id is not None


async def test_device_scanner_update_to_away_nulls_properties(
    hass: HomeAssistant,
    mock_omada_clients_only_site_client: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test gateway connected switches."""

    entity_id = "device_tracker.banana"

    updated_entity = entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert not updated_entity.disabled
    async_fire_time_changed(hass, utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    await _setup_client_disconnect(
        mock_omada_clients_only_site_client, "2C-71-FF-ED-34-83"
    )

    async_fire_time_changed(hass, utcnow() + (POLL_INTERVAL * 2))
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity == snapshot

    mock_omada_clients_only_site_client.get_connected_clients.assert_called_once()


async def _setup_client_disconnect(
    mock_omada_site_client: MagicMock,
    client_mac: str,
):
    original_clients = [
        c
        async for c in mock_omada_site_client.get_connected_clients()
        if c.mac != client_mac
    ]

    async def get_filtered_clients() -> AsyncIterable[OmadaConnectedClient]:
        for c in original_clients:
            yield c

    mock_omada_site_client.get_connected_clients.reset_mock()
    mock_omada_site_client.get_connected_clients.side_effect = get_filtered_clients
