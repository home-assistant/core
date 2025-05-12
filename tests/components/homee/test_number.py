"""Test Homee nmumbers."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def setup_numbers(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the number platform."""
    mock_homee.nodes = [build_mock_node("numbers.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("number.test_number_down_position", 100.0),
        ("number.test_number_threshold_for_wind_trigger", 5.0),
    ],
)
async def test_value_fn(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected: float,
) -> None:
    """Test the value_fn of the number entity."""
    await setup_numbers(hass, mock_homee, mock_config_entry)

    assert hass.states.get(entity_id).state == str(expected)


@pytest.mark.parametrize(
    ("entity_id", "attribute_index", "value", "expected"),
    [
        ("number.test_number_down_position", 0, 90, 90),
        ("number.test_number_threshold_for_wind_trigger", 15, 7.5, 3),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    attribute_index: int,
    value: float,
    expected: float,
) -> None:
    """Test set_value service."""
    await setup_numbers(hass, mock_homee, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )
    number = mock_homee.nodes[0].attributes[attribute_index]
    mock_homee.set_value.assert_called_once_with(number.node_id, number.id, expected)


async def test_set_value_not_editable(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set_value if attribute is not editable."""
    await setup_numbers(hass, mock_homee, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number_motion_alarm_delay", ATTR_VALUE: 10000},
        blocking=True,
    )
    assert not mock_homee.set_value.called
    assert not hass.states.async_available("number.test_number_motion_alarm_delay")


async def test_number_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the multisensor snapshot."""
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.NUMBER]):
        await setup_numbers(hass, mock_homee, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
