"""Tests for the Concord232 binary sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.concord232.binary_sensor import SCAN_INTERVAL
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_zone_sensors_created(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test one binary sensor is created per zone."""
    await setup_integration(hass, mock_config_entry)

    front_door = hass.states.get("binary_sensor.front_door")
    assert front_door is not None
    assert front_door.state == STATE_OFF
    assert front_door.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.OPENING

    motion = hass.states.get("binary_sensor.hall_motion")
    assert motion is not None
    assert motion.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.MOTION


@pytest.mark.parametrize(
    ("zone_name", "expected_class"),
    [
        ("SIDE MOTION", BinarySensorDeviceClass.MOTION),
        ("FIRE KEY", BinarySensorDeviceClass.SAFETY),
        ("HALL SMOKE", BinarySensorDeviceClass.SMOKE),
        ("FRONT DOOR", BinarySensorDeviceClass.OPENING),
    ],
)
async def test_device_class_guessing(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    zone_name: str,
    expected_class: BinarySensorDeviceClass,
) -> None:
    """Test the device class is guessed from the zone name."""
    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": zone_name, "state": "Normal"}
    ]
    await setup_integration(hass, mock_config_entry)

    entity_id = f"binary_sensor.{zone_name.lower().replace(' ', '_')}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_DEVICE_CLASS] == expected_class


async def test_zone_state_updates(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a tripped zone turns the sensor on at the next poll."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("binary_sensor.front_door").state == STATE_OFF

    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": "FRONT DOOR", "state": "Tripped"},
        {"number": 2, "name": "HALL MOTION", "state": "Normal"},
    ]
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.front_door").state == STATE_ON


async def test_unsorted_zones_map_to_stable_entities(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zones are sorted by number regardless of server order."""
    mock_concord232_client.list_zones.return_value = [
        {"number": 2, "name": "HALL MOTION", "state": "Normal"},
        {"number": 1, "name": "FRONT DOOR", "state": "Tripped"},
    ]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.front_door").state == STATE_ON
    assert hass.states.get("binary_sensor.hall_motion").state == STATE_OFF
