"""Tests for TP-Link Omada device tracker entities."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion
from tplink_omada_client.exceptions import RequestFailed

from homeassistant.components.tplink_omada.config_flow import (
    OPT_DEVICE_TRACKER,
    OPT_SCANNED_CLIENTS,
    OPT_TRACKED_CLIENTS,
)
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import POLL_CLIENTS
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

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
        options={
            OPT_DEVICE_TRACKER: True,
            OPT_TRACKED_CLIENTS: ["2E-DC-E1-C4-37-D3"],
            OPT_SCANNED_CLIENTS: ["2C-71-FF-ED-34-83"],
        },
        unique_id="12345",
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


async def test_device_tracker_created(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test gateway connected switches."""

    entity_id = "device_tracker.apple"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity == snapshot


async def test_device_scanner_created(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test gateway connected switches."""

    entity_id = "device_tracker.banana"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity == snapshot


async def test_device_scanner_created_with_default_name(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_omada_clients_only_site_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test gateway connected switches."""

    mock_omada_clients_only_site_client.get_client.side_effect = RequestFailed(
        error_code=1001, msg="Some poor reason"
    )

    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        options={
            OPT_DEVICE_TRACKER: True,
            OPT_TRACKED_CLIENTS: [],
            OPT_SCANNED_CLIENTS: ["2C-71-FF-ED-34-83"],
        },
        unique_id="12345",
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "device_tracker.2C_71_FF_ED_34_83"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity == snapshot


async def test_device_tracker_update_to_away_nulls_properties(
    hass: HomeAssistant,
    mock_omada_clients_only_site_client: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test gateway connected switches."""

    entity_id = "device_tracker.apple"
    entity = hass.states.get(entity_id)
    await _setup_client_disconnect(
        mock_omada_clients_only_site_client, "2E-DC-E1-C4-37-D3"
    )

    async_fire_time_changed(hass, utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done()

    mock_omada_clients_only_site_client.get_connected_clients.assert_called_once()

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity == snapshot


async def test_device_scanner_update_to_away_nulls_properties(
    hass: HomeAssistant,
    mock_omada_clients_only_site_client: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test gateway connected switches."""

    entity_id = "device_tracker.banana"
    entity = hass.states.get(entity_id)
    await _setup_client_disconnect(
        mock_omada_clients_only_site_client, "2C-71-FF-ED-34-83"
    )

    async_fire_time_changed(hass, utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done()

    mock_omada_clients_only_site_client.get_connected_clients.assert_called_once()

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity == snapshot


async def _setup_client_disconnect(
    mock_omada_site_client: MagicMock,
    client_mac: str,
):
    filtered_clients = [
        c
        async for c in mock_omada_site_client.get_connected_clients()
        if c.mac != client_mac
    ]
    mock_omada_site_client.get_connected_clients.reset_mock()
    mock_omada_site_client.get_connected_clients.return_value = filtered_clients
