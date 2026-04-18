"""Tests for the Compit number platform."""

from typing import Any
from unittest.mock import MagicMock

from compit_inext_api.consts import CompitParameter
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_compit_entities

from tests.common import MockConfigEntry


async def test_number_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test for number entities creation, unique IDs, and device info."""
    await setup_integration(hass, mock_config_entry)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.NUMBER)


@pytest.mark.parametrize(
    "mock_return_value",
    [
        None,
        "invalid",
    ],
)
async def test_number_unknown_device_parameters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    mock_return_value: Any,
) -> None:
    """Test that number entity shows unknown when get_parameter_value returns invalid values."""

    mock_connector.get_current_value.side_effect = lambda device_id, parameter_code: (
        mock_return_value
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.nano_color_2_target_comfort_temperature")
    assert state is not None
    assert state.state == "unknown"


async def test_number_get_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test getting a number value."""
    mock_connector.get_current_value.side_effect = lambda device_id, parameter_code: (
        22.0
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.nano_color_2_target_comfort_temperature")
    assert state is not None
    assert state.state == "22.0"


async def test_set_number_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test setting a number value."""

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.nano_color_2_target_comfort_temperature")
    assert state is not None

    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: state.entity_id, "value": 23},
        blocking=True,
    )

    mock_connector.set_device_parameter.assert_called_once_with(
        2, CompitParameter.TARGET_TEMPERATURE_COMFORT, 23
    )
