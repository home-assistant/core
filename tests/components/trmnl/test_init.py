"""Test the TRMNL initialization."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion
from trmnl.exceptions import TRMNLAuthenticationError

from homeassistant.components.trmnl.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the TRMNL device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, "B0:A6:04:AA:BB:CC")}
    )
    assert device
    assert device == snapshot


async def test_stale_device_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device is removed from the device registry when it disappears."""
    await setup_integration(hass, mock_config_entry)

    assert device_registry.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, "B0:A6:04:AA:BB:CC")}
    )

    mock_trmnl_client.get_devices.return_value = []
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, "B0:A6:04:AA:BB:CC")}
    )


async def test_reauth_triggered_on_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test that a reauth flow is triggered when an auth error occurs."""
    mock_trmnl_client.get_devices.side_effect = TRMNLAuthenticationError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "user"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id
