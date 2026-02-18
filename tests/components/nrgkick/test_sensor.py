"""Tests for the NRGkick sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from nrgkick_api import ChargingStatus, ConnectorType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

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
