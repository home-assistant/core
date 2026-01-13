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
    await setup_integration(hass, mock_config_entry)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize(
    ("mock_return_value", "test_description"),
    [
        (None, "parameter is None"),
        (MagicMock(value=None), "parameter value is None"),
        (MagicMock(value=999), "parameter value not in options"),
    ],
)
async def test_select_unknown_device_parameters(
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
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.operation_mode")
    assert state is not None
    assert state.state == "unknown"


async def test_select_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test selecting an option."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.operation_mode", "option": "Auto"},
        blocking=False,
    )

    mock_connector.set_device_parameter.assert_called_once()
    assert (
        mock_connector.get_device_parameter(1, "op_mode").value == 0
    )  # 0 is Auto, it was Manual before


async def test_select_invalid_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test selecting an invalid option."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.operation_mode", "option": "Invalid"},
        blocking=False,
    )

    mock_connector.set_device_parameter.assert_not_called()
