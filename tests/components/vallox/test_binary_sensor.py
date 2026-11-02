"""Tests for Vallox binary sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.mark.usefixtures("mock_vallox_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the binary sensor entities."""
    with patch("homeassistant.components.vallox.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [
        pytest.param({"A_CYC_IO_HEATER": 1}, STATE_ON, id="on"),
        pytest.param({"A_CYC_IO_HEATER": 0}, STATE_OFF, id="off"),
    ],
)
async def test_post_heater_binary_sensor(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    expected_state: str,
) -> None:
    """Test the post heater binary sensor."""
    mock_vallox_client.fetch_metric_data.assert_called_once()
    state = hass.states.get("binary_sensor.vallox_post_heater")
    assert state
    assert state.state == expected_state
