"""Tests for the AquaLogic sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aqualogic.const import UPDATE_TOPIC
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_processor: MagicMock,
) -> None:
    """Test sensor entities are created and report correct state."""
    async_dispatcher_send(hass, UPDATE_TOPIC)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_sensors_imperial_units(
    hass: HomeAssistant,
    mock_processor: MagicMock,
) -> None:
    """Test sensors report imperial units when the panel is not metric."""
    mock_processor.panel.is_metric = False
    async_dispatcher_send(hass, UPDATE_TOPIC)
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
    async_dispatcher_send(hass, UPDATE_TOPIC)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.aqualogic_air_temperature").state == "25.5"

    mock_processor.panel = None
    async_dispatcher_send(hass, UPDATE_TOPIC)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aqualogic_air_temperature").state == STATE_UNKNOWN
