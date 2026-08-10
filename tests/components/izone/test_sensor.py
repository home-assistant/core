"""Tests for iZone sensor platform."""

from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.izone.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

SUPPLY_ENTITY = "sensor.izone_controller_000000001_supply_temperature"
RETURN_ENTITY = "sensor.izone_controller_000000001_return_temperature"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the sensor platform for these tests."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Controller supply and return temperature sensors are created."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_sensor_device_linked_to_controller(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Temperature sensors are attached to the controller device."""
    controller_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "000000001"), mock_config_entry.entry_id
    )
    assert controller_device is not None

    for entity_id in (SUPPLY_ENTITY, RETURN_ENTITY):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == controller_device.id


@pytest.mark.usefixtures("mock_create_discovery")
async def test_sensor_unknown_when_temp_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: Mock,
) -> None:
    """Missing supply/return temps report as unknown."""
    mock_controller.temp_supply = None
    mock_controller.temp_return = None

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SUPPLY_ENTITY).state == STATE_UNKNOWN
    assert hass.states.get(RETURN_ENTITY).state == STATE_UNKNOWN
