"""Tests for the NRGkick sensor platform."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from nrgkick_api import ChargingStatus, ConnectorType
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nrgkick.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


@pytest.mark.freeze_time("2023-10-21")
async def test_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entities."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_mapped_unknown_values_become_state_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test that enum-like UNKNOWN values map to HA's unknown state."""

    mock_nrgkick_api.get_info.return_value["connector"]["type"] = ConnectorType.UNKNOWN
    mock_nrgkick_api.get_values.return_value["general"]["status"] = (
        ChargingStatus.UNKNOWN
    )

    await setup_integration(hass, mock_config_entry, platforms=[Platform.SENSOR])

    assert (state := hass.states.get("sensor.nrgkick_test_connector_type"))
    assert state.state == STATE_UNKNOWN
    assert (state := hass.states.get("sensor.nrgkick_test_status"))
    assert state.state == STATE_UNKNOWN


async def test_cellular_and_gps_entities_are_gated_by_model_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test that cellular entities are only created for SIM-capable models."""

    mock_nrgkick_api.get_info.return_value["general"]["model_type"] = "NRGkick Gen2"

    await setup_integration(hass, mock_config_entry, platforms=[Platform.SENSOR])

    assert hass.states.get("sensor.nrgkick_test_cellular_mode") is None
    assert hass.states.get("sensor.nrgkick_test_cellular_signal_strength") is None
    assert hass.states.get("sensor.nrgkick_test_cellular_operator") is None


async def test_vehicle_connected_since_none_when_standby(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test vehicle connected since is unknown when vehicle is not connected."""
    mock_nrgkick_api.get_values.return_value["general"]["status"] = (
        ChargingStatus.STANDBY
    )

    await setup_integration(hass, mock_config_entry, platforms=[Platform.SENSOR])

    assert (state := hass.states.get("sensor.nrgkick_test_vehicle_connected_since"))
    assert state.state == STATE_UNKNOWN


async def test_power_factor_is_converted_to_percent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test that the power factor ratio from the device is shown in percent."""
    powerflow = mock_nrgkick_api.get_values.return_value["powerflow"]
    powerflow["l1"]["power_factor"] = -0.182
    powerflow["total_power_factor"] = None

    await setup_integration(hass, mock_config_entry, platforms=[Platform.SENSOR])

    assert (state := hass.states.get("sensor.nrgkick_test_l1_power_factor"))
    assert state.state == "-18.2"
    assert (state := hass.states.get("sensor.nrgkick_test_total_power_factor"))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("connector_type", "phase_count", "available"),
    [
        (
            ConnectorType.TYPE2,
            3,
            {
                "connector_l1_temperature": True,
                "connector_l2_temperature": True,
                "connector_l3_temperature": True,
                "domestic_plug_1_temperature": False,
                "domestic_plug_2_temperature": False,
            },
        ),
        (
            ConnectorType.DOMESTIC,
            1,
            {
                "connector_l1_temperature": True,
                "connector_l2_temperature": False,
                "connector_l3_temperature": False,
                "domestic_plug_1_temperature": True,
                "domestic_plug_2_temperature": True,
            },
        ),
        (
            ConnectorType.TYPE2,
            None,
            {
                "connector_l1_temperature": True,
                "connector_l2_temperature": True,
                "connector_l3_temperature": True,
                "domestic_plug_1_temperature": False,
                "domestic_plug_2_temperature": False,
            },
        ),
    ],
    ids=["type2_3_phases", "domestic_1_phase", "phase_count_missing"],
)
async def test_temperatures_depend_on_attachment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    connector_type: ConnectorType,
    phase_count: int | None,
    available: dict[str, bool],
) -> None:
    """Test that temperatures are only available if the attachment has them."""
    connector = mock_nrgkick_api.get_info.return_value["connector"]
    connector["type"] = connector_type
    if phase_count is None:
        del connector["phase_count"]
    else:
        connector["phase_count"] = phase_count

    await setup_integration(hass, mock_config_entry, platforms=[Platform.SENSOR])

    for key, is_available in available.items():
        assert (state := hass.states.get(f"sensor.nrgkick_test_{key}"))
        assert (state.state != STATE_UNAVAILABLE) is is_available, key


async def test_temperatures_follow_attachment_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that temperature availability follows a swapped attachment."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.SENSOR])

    assert (state := hass.states.get("sensor.nrgkick_test_domestic_plug_1_temperature"))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get("sensor.nrgkick_test_connector_l3_temperature"))
    assert state.state == "28.5"

    # Return new data, as the device does on each poll.
    info = deepcopy(mock_nrgkick_api.get_info.return_value)
    info["connector"]["type"] = ConnectorType.DOMESTIC
    info["connector"]["phase_count"] = 1
    mock_nrgkick_api.get_info.return_value = info
    values = deepcopy(mock_nrgkick_api.get_values.return_value)
    values["temperatures"]["domestic_plug_1"] = 31.5
    mock_nrgkick_api.get_values.return_value = values

    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.nrgkick_test_domestic_plug_1_temperature"))
    assert state.state == "31.5"
    assert (state := hass.states.get("sensor.nrgkick_test_connector_l3_temperature"))
    assert state.state == STATE_UNAVAILABLE
