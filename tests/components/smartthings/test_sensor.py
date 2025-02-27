"""Test for the SmartThings sensors platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_smartthings_entities, trigger_update

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SENSOR)


@pytest.mark.parametrize("device_fixture", ["aeotec_home_energy_meter_gen5"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.aeotec_energy_monitor_energy_2").state == "19978.536"

    await trigger_update(
        hass,
        devices,
        "f0af21a2-d5a1-437c-b10a-b34a87394b71",
        Capability.ENERGY_METER,
        Attribute.ENERGY,
        20000.0,
    )

    assert hass.states.get("sensor.aeotec_energy_monitor_energy_2").state == "20000.0"
