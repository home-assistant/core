"""Tests for the Compit select platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_compit_entities

from tests.common import MockConfigEntry


async def test_select_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test for select entities creation, unique IDs, and device info."""
    await setup_integration(hass, mock_config_entry, mock_connector)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.SELECT)


async def test_select_valid_scenarios(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test that select entity shows valid options when get_device_parameter returns valid values."""
    mock_connector.get_device_parameter.side_effect = (
        lambda device_id, parameter_code: MagicMock(value=1)
    )
    await setup_integration(hass, mock_config_entry, mock_connector)

    state = hass.states.get("select.operation_mode")
    assert state is not None
    assert state.state == "Manual"


@pytest.mark.parametrize(
    ("mock_return_value", "test_description"),
    [
        (None, "parameter is None"),
        (MagicMock(value=None), "parameter value is None"),
        (MagicMock(value=999), "parameter value not in options"),
    ],
)
async def test_select_unknown_scenarios(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    mock_return_value: MagicMock | None,
    test_description: str,
) -> None:
    """Test that select entity shows unknown when get_device_parameter returns various invalid values."""
    mock_connector.get_device_parameter.side_effect = (
        lambda device_id, parameter_code: mock_return_value
    )
    await setup_integration(hass, mock_config_entry, mock_connector)

    state = hass.states.get("select.operation_mode")
    assert state is not None
    assert state.state == "unknown"


async def test_select_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test selecting an option."""
    current_value = MagicMock(value=1)

    def set_param(device_id, parameter_code, value):
        current_value.value = value
        return True

    mock_connector.set_device_parameter.side_effect = set_param

    await setup_integration(hass, mock_config_entry, mock_connector)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.operation_mode", "option": "Auto"},
        blocking=False,
    )

    mock_connector.set_device_parameter.assert_called_once()
    state = hass.states.get("select.operation_mode")
    assert state is not None
    assert current_value.value == 0  # 0 is Auto
