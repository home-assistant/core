"""Test homee sensors."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homee.const import (
    DOMAIN,
    OPEN_CLOSE_MAP,
    OPEN_CLOSE_MAP_REVERSED,
    WINDOW_MAP,
    WINDOW_MAP_REVERSED,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import async_update_attribute_value, build_mock_node, setup_integration
from .conftest import HOMEE_ID

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def setup_sensor(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Setups the integration for sensor tests."""
    mock_homee.nodes = [build_mock_node("sensors.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)


async def test_up_down_values(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test values for up/down sensor."""
    await setup_sensor(hass, mock_homee, mock_config_entry)

    assert hass.states.get("sensor.test_multisensor_state").state == OPEN_CLOSE_MAP[0]

    attribute = mock_homee.nodes[0].attributes[28]
    for i in range(1, 5):
        await async_update_attribute_value(hass, attribute, i)
        assert (
            hass.states.get("sensor.test_multisensor_state").state == OPEN_CLOSE_MAP[i]
        )

    # Test reversed up/down sensor
    attribute.is_reversed = True
    for i in range(5):
        await async_update_attribute_value(hass, attribute, i)
        assert (
            hass.states.get("sensor.test_multisensor_state").state
            == OPEN_CLOSE_MAP_REVERSED[i]
        )


async def test_window_position(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test values for window handle position."""
    await setup_sensor(hass, mock_homee, mock_config_entry)

    assert (
        hass.states.get("sensor.test_multisensor_window_position").state
        == WINDOW_MAP[0]
    )

    attribute = mock_homee.nodes[0].attributes[33]
    for i in range(1, 3):
        await async_update_attribute_value(hass, attribute, i)
        assert (
            hass.states.get("sensor.test_multisensor_window_position").state
            == WINDOW_MAP[i]
        )

    # Test reversed window handle.
    attribute.is_reversed = True
    for i in range(3):
        await async_update_attribute_value(hass, attribute, i)
        assert (
            hass.states.get("sensor.test_multisensor_window_position").state
            == WINDOW_MAP_REVERSED[i]
        )


@pytest.mark.parametrize(
    ("disabler", "expected_entity", "expected_issue"),
    [
        (None, False, False),
        (er.RegistryEntryDisabler.USER, True, True),
    ],
)
async def test_sensor_deprecation(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    disabler: er.RegistryEntryDisabler,
    expected_entity: bool,
    expected_issue: bool,
) -> None:
    """Test sensor deprecation issue."""
    entity_uid = f"{HOMEE_ID}-1-9"
    entity_id = "test_multisensor_valve_position"
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        entity_uid,
        suggested_object_id=entity_id,
        disabled_by=disabler,
    )

    with patch(
        "homeassistant.components.homee.sensor.entity_used_in", return_value=True
    ):
        await setup_sensor(hass, mock_homee, mock_config_entry)

    assert (entity_registry.async_get(f"sensor.{entity_id}") is None) is expected_entity
    assert (
        issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_entity_{entity_uid}",
        )
        is None
    ) is expected_issue


async def test_sensor_deprecation_unused_entity(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor deprecation issue."""
    entity_uid = f"{HOMEE_ID}-1-9"
    entity_id = "test_multisensor_valve_position"
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        entity_uid,
        suggested_object_id=entity_id,
        disabled_by=None,
    )

    await setup_sensor(hass, mock_homee, mock_config_entry)

    assert entity_registry.async_get(f"sensor.{entity_id}") is not None
    assert (
        issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_entity_{entity_uid}",
        )
        is None
    )


async def test_sensor_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the multisensor snapshot."""
    mock_homee.nodes = [build_mock_node("sensors.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
