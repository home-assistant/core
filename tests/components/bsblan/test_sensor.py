"""Tests for the BSB-LAN sensor platform."""

from unittest.mock import AsyncMock

from bsblan import (
    BSBLANAuthError,
    BSBLANConnectionError,
    BSBLANError,
    BSBLANMalformedResponseError,
    Device,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_CURRENT_TEMP = "sensor.bsb_lan_current_temperature"
ENTITY_OUTSIDE_TEMP = "sensor.bsb_lan_outside_temperature"
ENTITY_TOTAL_ENERGY = "sensor.bsb_lan_total_energy"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor entity properties."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_not_created_when_data_unavailable(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors are not created when sensor data is not available."""
    # Set all sensor data to None to simulate no sensors available
    mock_bsblan.sensor.return_value.current_temperature = None
    mock_bsblan.sensor.return_value.outside_temperature = None
    mock_bsblan.sensor.return_value.total_energy = None

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    # Should not create any sensor entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entities = [entry for entry in entity_entries if entry.domain == "sensor"]
    assert len(sensor_entities) == 0


async def test_sensors_not_created_when_sensor_request_fails(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors are not created when generic sensor data is unsupported."""
    mock_bsblan.device.return_value = Device.model_validate(
        {**mock_bsblan.device.return_value.model_dump(), "bus": "PPS"}
    )
    mock_bsblan.sensor.side_effect = BSBLANError("No sensor data")

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert mock_config_entry.runtime_data.fast_coordinator.data.sensor.model_dump() == {
        "current_temperature": None,
        "outside_temperature": None,
        "total_energy": None,
    }

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entities = [entry for entry in entity_entries if entry.domain == "sensor"]
    assert len(sensor_entities) == 0


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        pytest.param(
            BSBLANError("Sensor failed"), ConfigEntryState.SETUP_RETRY, id="generic"
        ),
        pytest.param(
            BSBLANConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
            id="connection",
        ),
        pytest.param(
            BSBLANAuthError("Authentication failed"),
            ConfigEntryState.SETUP_ERROR,
            id="auth",
        ),
    ],
)
async def test_sensor_errors_fail_setup(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: BSBLANError,
    expected_state: ConfigEntryState,
) -> None:
    """Test sensor failures are not treated as successful updates."""
    mock_bsblan.sensor.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("bus", "exception"),
    [
        pytest.param("BSB", BSBLANError("Sensor failed"), id="bsb-generic"),
        pytest.param(
            "PPS",
            BSBLANMalformedResponseError("Malformed sensor response"),
            id="pps-malformed",
        ),
    ],
)
async def test_sensor_error_on_refresh_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    bus: str,
    exception: BSBLANError,
) -> None:
    """Test a failed sensor refresh does not expose stale values as available."""
    mock_bsblan.device.return_value = Device.model_validate(
        {**mock_bsblan.device.return_value.model_dump(), "bus": bus}
    )
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])
    state = hass.states.get(ENTITY_CURRENT_TEMP)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    mock_bsblan.sensor.reset_mock()
    mock_bsblan.sensor.side_effect = exception
    freezer.tick(delta=20)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_bsblan.sensor.assert_awaited_once()
    assert not mock_config_entry.runtime_data.fast_coordinator.last_update_success
    state = hass.states.get(ENTITY_CURRENT_TEMP)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_partial_sensors_created_when_some_data_available(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test only available sensors are created when some sensor data is available."""
    # Only current temperature available, outside temperature and energy not
    mock_bsblan.sensor.return_value.outside_temperature = None
    mock_bsblan.sensor.return_value.total_energy = None

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    # Should create only the current temperature sensor
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entities = [entry for entry in entity_entries if entry.domain == "sensor"]
    assert len(sensor_entities) == 1
    assert sensor_entities[0].entity_id == ENTITY_CURRENT_TEMP
