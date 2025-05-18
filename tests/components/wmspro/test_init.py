"""Test the wmspro initialization."""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.wmspro.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_config_entry

from tests.common import MockConfigEntry


async def test_config_entry_device_config_ping_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
) -> None:
    """Test that a config entry will be retried due to ConfigEntryNotReady."""
    mock_hub_ping.side_effect = aiohttp.ClientError
    await setup_config_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert len(mock_hub_ping.mock_calls) == 1


async def test_config_entry_device_config_refresh_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_refresh: AsyncMock,
) -> None:
    """Test that a config entry will be retried due to ConfigEntryNotReady."""
    mock_hub_refresh.side_effect = aiohttp.ClientError
    await setup_config_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_refresh.mock_calls) == 1


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [
        ("mock_hub_configuration_prod_awning_dimmer", "mock_hub_status_prod_awning"),
        ("mock_hub_configuration_prod_awning_dimmer", "mock_hub_status_prod_dimmer"),
        (
            "mock_hub_configuration_prod_roller_shutter",
            "mock_hub_status_prod_roller_shutter",
        ),
    ],
)
async def test_cover_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    request: pytest.FixtureRequest,
) -> None:
    """Test that the device is created correctly."""
    mock_hub_configuration = request.getfixturevalue(mock_hub_configuration)
    mock_hub_status = request.getfixturevalue(mock_hub_status)

    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) > 0

    device_entries = device_registry.devices.get_devices_for_config_entry_id(
        mock_config_entry.entry_id
    )
    assert len(device_entries) > 1

    device_entries = list(
        filter(
            lambda e: e.identifiers != {(DOMAIN, mock_config_entry.entry_id)},
            device_entries,
        )
    )
    assert len(device_entries) > 0
    for device_entry in device_entries:
        assert device_entry == snapshot(name=f"device-{device_entry.serial_number}")
