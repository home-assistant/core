"""Velbus sensor platform tests."""

from unittest.mock import AsyncMock, PropertyMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_vmb8in_counter_energy_unavailable_when_no_energy(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_buttoncounter: AsyncMock,
) -> None:
    """Test VMB8IN-20 counter sensor is unknown when energy has not been received."""
    type(mock_buttoncounter).energy = PropertyMock(return_value=None)
    await init_integration(hass, config_entry)

    state = hass.states.get("sensor.input_buttoncounter_counter")
    assert state is not None
    assert state.state == STATE_UNKNOWN
