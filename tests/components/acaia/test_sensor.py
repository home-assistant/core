"""Test sensors for acaia integration."""

from unittest.mock import MagicMock

from syrupy import SnapshotAssertion

from homeassistant import core as ha
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data

SENSORS = ("weight", "battery")


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the acaia sensors."""
    await setup_integration(hass, mock_config_entry, mock_scale)

    for sensor in SENSORS:
        state = hass.states.get(f"sensor.lunar_123456_{sensor}")
        assert state
        assert state == snapshot(name=f"state_sensor_{sensor}")

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry == snapshot(name=f"entry_sensor_{sensor}")


async def test_restore_state(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test battery sensor restore state."""
    mock_scale.device_state = None

    entity_id = "sensor.lunar_123456_battery"
    fake_state = ha.State(
        entity_id,
        "",
    )
    fake_extra_data = {
        "native_value": 65,
        "native_unit_of_measurement": PERCENTAGE,
    }
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))

    await setup_integration(hass, mock_config_entry, mock_scale)

    state = hass.states.get(entity_id)
    assert state.state == str(65)
