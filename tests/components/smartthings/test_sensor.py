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


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.ac_office_granit_temperature").state == "25"

    await trigger_update(
        hass,
        devices,
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.TEMPERATURE_MEASUREMENT,
        Attribute.TEMPERATURE,
        20,
    )

    assert hass.states.get("sensor.ac_office_granit_temperature").state == "20"
