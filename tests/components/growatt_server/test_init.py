"""Tests for the Growatt Server integration."""

from datetime import timedelta
import json

from freezegun.api import FrozenDateTimeFactory
import growattServer
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.growatt_server.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("init_integration")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("init_integration")
async def test_device_info(
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "MIN123456")})
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (growattServer.GrowattV1ApiError("API Error"), ConfigEntryState.SETUP_ERROR),
        (
            json.decoder.JSONDecodeError("Invalid JSON", "", 0),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_setup_error_on_api_failure(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup error on API failures during device list."""
    mock_growatt_v1_api.device_list.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles update failures gracefully."""
    # Integration should be loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Cause coordinator update to fail
    mock_growatt_v1_api.min_detail.side_effect = growattServer.GrowattV1ApiError(
        "Connection timeout"
    )

    # Trigger coordinator refresh
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Integration should remain loaded despite coordinator error
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_classic_api_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test integration setup with Classic API (password auth)."""
    # Classic API doesn't support MIN devices - use TLX device instead
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.LOADED

    # Verify Classic API login was called
    mock_growatt_classic_api.login.assert_called()

    # Verify device was created
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "TLX123456")})
    assert device_entry is not None
    assert device_entry == snapshot
