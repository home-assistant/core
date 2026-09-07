"""Tests for NexBlue sensors."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from nexblue_api import NexBlueConnectionError, NexBlueDeviceOfflineError, NexBlueError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import CHARGER, CHARGER_STATUS

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensor_entities_snapshot(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the complete NexBlue sensor platform through a snapshot."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        init_integration.entry_id,
    )


async def test_missing_phase_values_are_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test missing phase measurements are exposed as unknown."""
    mock_client.async_get_charger_status.return_value = replace(
        CHARGER_STATUS,
        current_a=(16.0,),
        voltage_v=(230,),
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.nb123456_current_l1").state == "16.0"
    assert hass.states.get("sensor.nb123456_current_l2").state == STATE_UNKNOWN
    assert hass.states.get("sensor.nb123456_voltage_l1").state == "230"
    assert hass.states.get("sensor.nb123456_voltage_l3").state == STATE_UNKNOWN


@pytest.mark.parametrize("error", [NexBlueDeviceOfflineError, NexBlueError])
async def test_charger_error_does_not_block_other_chargers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: type[Exception],
) -> None:
    """Test a single charger error does not prevent other chargers updating."""
    second_charger = type(CHARGER)(serial_number="NB654321")
    mock_client.async_list_chargers.return_value = [CHARGER, second_charger]
    mock_client.async_get_charger_status.side_effect = [
        CHARGER_STATUS,
        error,
    ]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.nb123456_charging_state").state == "charging"
    assert hass.states.get("sensor.nb654321_charging_state").state == STATE_UNAVAILABLE


async def test_sensors_unavailable_when_coordinator_update_fails(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed coordinator update makes all charger entities unavailable."""
    mock_client.async_list_chargers.side_effect = NexBlueConnectionError

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.nb123456_charging_state").state == STATE_UNAVAILABLE
