"""Tests for the NRGkick sensor platform."""

from datetime import datetime
import json
from typing import Any
from unittest.mock import patch

from nrgkick_api import ChargingStatus, ConnectorType, GridPhases
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import dt as dt_util

from . import async_setup_integration

from tests.common import load_fixture, snapshot_platform

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


@pytest.fixture
def mock_values_data_sensor() -> dict[str, Any]:
    """Mock values data for sensor tests."""
    return json.loads(load_fixture("values_sensor.json", DOMAIN))


async def test_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data_sensor,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entities."""

    # Make enum-like info fields numeric as well (these are mapped via tables).
    mock_info_data["connector"]["type"] = ConnectorType.TYPE2
    mock_info_data["grid"]["phases"] = GridPhases.L1_L2_L3

    # Setup mock data
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data_sensor

    # Setup entry
    now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.components.nrgkick.sensor.utcnow", return_value=now):
        await async_setup_integration(hass, mock_config_entry)

    def get_entity_id_by_key(key: str) -> str:
        unique_id = f"TEST123456_{key}"
        entity_id = entity_registry.async_get_entity_id("sensor", "nrgkick", unique_id)
        assert entity_id is not None
        return entity_id

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Defensive: if the API returns an unexpected type for a nested section,
    # the entity should fall back to unknown (native_value=None).
    bad_values: dict[str, Any] = dict(mock_values_data_sensor)
    bad_values["powerflow"] = "not-a-dict"
    mock_nrgkick_api.get_values.return_value = bad_values

    await async_update_entity(hass, get_entity_id_by_key("charging_current"))
    await hass.async_block_till_done()

    state = hass.states.get(get_entity_id_by_key("charging_current"))
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_mapped_unknown_values_become_state_unknown(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data_sensor,
) -> None:
    """Test that enum-like UNKNOWN values map to HA's unknown state."""

    mock_info_data["connector"]["type"] = ConnectorType.UNKNOWN
    mock_info_data["grid"]["phases"] = GridPhases.UNKNOWN
    mock_values_data_sensor["general"]["status"] = ChargingStatus.UNKNOWN

    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data_sensor

    await async_setup_integration(hass, mock_config_entry)

    entity_registry: er.EntityRegistry = er.async_get(hass)

    def get_state_by_key(key: str) -> State | None:
        unique_id = f"TEST123456_{key}"
        entity_id = entity_registry.async_get_entity_id("sensor", "nrgkick", unique_id)
        return hass.states.get(entity_id) if entity_id else None

    for key in ("connector_type", "status"):
        state = get_state_by_key(key)
        assert state is not None
        assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("model_type", "expect_optional_entities"),
    [
        ("NRGkick Gen2", False),
        ("NRGkick Gen2 SIM", True),
    ],
)
async def test_cellular_and_gps_entities_are_gated_by_model_type(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data_sensor,
    model_type: str,
    expect_optional_entities: bool,
) -> None:
    """Test that cellular/GPS entities are only created for SIM-capable models (GPS to be added later)."""

    mock_info_data["general"]["model_type"] = model_type

    # Include example payload sections. Even if values are missing/None, the
    # sensors should still be created when the model supports the modules.
    mock_info_data["cellular"] = {"mode": None, "rssi": None, "operator": None}

    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data_sensor

    await async_setup_integration(hass, mock_config_entry)

    entity_registry = er.async_get(hass)
    optional_keys = (
        "cellular_mode",
        "cellular_rssi",
        "cellular_operator",
    )
    for key in optional_keys:
        unique_id = f"TEST123456_{key}"
        entity_id = entity_registry.async_get_entity_id("sensor", "nrgkick", unique_id)
        if expect_optional_entities:
            assert entity_id is not None, f"{model_type}: expected {key} to be created"
        else:
            assert entity_id is None, (
                f"{model_type}: did not expect {key} to be created"
            )
