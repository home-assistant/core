"""Test the Sunsynk integration setup."""

from unittest.mock import AsyncMock

import pytest
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_sunsynk_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry loads and unloads."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("method", "exception", "result"),
    [
        ("get_inverters", SunsynkConnectionError, ConfigEntryState.SETUP_RETRY),
        ("get_inverters", SunsynkAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (
            "get_inverter_realtime_grid",
            SunsynkConnectionError,
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "get_inverter_realtime_grid",
            SunsynkAuthenticationError,
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_sunsynk_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    exception: Exception,
    result: ConfigEntryState,
) -> None:
    """Test the config entry retries when the API cannot be reached."""
    getattr(mock_sunsynk_client, method).side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is result


@pytest.mark.usefixtures("mock_sunsynk_client")
async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a device is created for each inverter."""
    await setup_integration(hass, mock_config_entry)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 3
    assert devices == snapshot
