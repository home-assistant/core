"""Tests for the AquaLogic sensor platform."""

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aqualogic import DOMAIN, AquaLogicProcessor
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def init_sensors(
    hass: HomeAssistant, init_integration: AquaLogicProcessor
) -> None:
    """Set up the AquaLogic sensor platform."""
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": DOMAIN}},
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_sensors")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    update_callback: Callable[[], None],
) -> None:
    """Test all sensor entities are created and report correct state."""
    update_callback()
    await hass.async_block_till_done()

    states = {
        state.entity_id: state
        for state in sorted(hass.states.async_all("sensor"), key=lambda s: s.entity_id)
    }
    assert states == snapshot


@pytest.mark.usefixtures("init_sensors")
async def test_sensors_imperial_units(
    hass: HomeAssistant,
    update_callback: Callable[[], None],
    mock_panel: MagicMock,
) -> None:
    """Test sensors report imperial units when the panel is not metric."""
    mock_panel.is_metric = False
    update_callback()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.aqualogic_salt_level")
    assert state.attributes["unit_of_measurement"] == "PPM"
