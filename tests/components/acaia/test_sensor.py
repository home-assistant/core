"""Test sensors for acaia integration."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import PERCENTAGE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)


async def test_sensors(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Acaia sensors."""
    with patch("homeassistant.components.acaia.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_restore_state(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test battery sensor restore state."""
    mock_scale.device_state = None
    entity_id = "sensor.lunar_ddeeff_battery"

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    entity_id,
                    "1",
                ),
                {
                    "native_value": 65,
                    "native_unit_of_measurement": PERCENTAGE,
                },
            ),
        ),
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "65"


async def test_battery_available_within_session_after_disconnect(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test battery stays available on disconnect when no restore data exists."""
    entity_id = "sensor.lunar_ddeeff_battery"

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "42"

    mock_scale.connected = False
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "42"
