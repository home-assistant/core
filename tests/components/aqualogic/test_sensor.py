"""Tests for the AquaLogic sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_sensors(
    hass: HomeAssistant,
    mock_processor: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entities are created and report correct state."""
    mock_processor.data_changed(mock_processor.panel)
    await hass.async_block_till_done()

    states = {
        state.entity_id: state
        for state in sorted(hass.states.async_all("sensor"), key=lambda s: s.entity_id)
    }
    assert states == snapshot


@pytest.mark.usefixtures("init_integration")
async def test_sensors_imperial_units(
    hass: HomeAssistant,
    mock_processor: MagicMock,
) -> None:
    """Test sensors report imperial units when the panel is not metric."""
    mock_processor.panel.is_metric = False
    mock_processor.data_changed(mock_processor.panel)
    await hass.async_block_till_done()

    # Use salt_level (g/L → PPM) to verify imperial branch without HA unit conversion
    state = hass.states.get("sensor.aqualogic_salt_level")
    assert state.attributes["unit_of_measurement"] == "PPM"


@pytest.mark.usefixtures("init_integration")
async def test_sensors_no_panel(
    hass: HomeAssistant,
    mock_processor: MagicMock,
) -> None:
    """Test sensors revert to unknown when the panel becomes unavailable."""
    mock_processor.data_changed(mock_processor.panel)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.aqualogic_air_temperature").state == "25.5"

    mock_processor.panel = None
    mock_processor.data_changed(None)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aqualogic_air_temperature").state == STATE_UNKNOWN
