"""Tests for the diagnostics data provided by the Sunricher DALI integration."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import DEVICE_DATA, _create_mock_device

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.fixture
def platforms() -> list[Platform]:
    """Keep init_integration setup minimal."""
    return []


@pytest.fixture
def mock_devices() -> list[MagicMock]:
    """Return a unique device list for a clean snapshot."""
    return [_create_mock_device(data) for data in DEVICE_DATA]


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics output matches the stored snapshot."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )


async def test_diagnostics_empty_runtime(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test diagnostics handles a gateway with zero devices and zero scenes."""
    mock_gateway.discover_devices.return_value = []
    mock_gateway.discover_scenes.return_value = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["devices"] == []
    assert result["scenes"] == []
    assert "entry_data" in result
