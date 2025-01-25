"""Tests for Vanderbilt SPC binary sensors."""

from typing import Final
from unittest.mock import PropertyMock

from pyspcwebgw.const import ZoneInput, ZoneType
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.spc.const import SIGNAL_UPDATE_SENSOR
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher

from .conftest import ZONE_DEFINITIONS

ZoneMapping = tuple[str, str, ZoneType, BinarySensorDeviceClass]

ZONE_ID_TO_CONFIG: Final[dict[str, tuple[str, ZoneType, BinarySensorDeviceClass]]] = {
    "1": ("entrance", ZoneType.ENTRY_EXIT, BinarySensorDeviceClass.OPENING),
    "2": ("living_room", ZoneType.ALARM, BinarySensorDeviceClass.MOTION),
    "3": ("smoke_sensor", ZoneType.FIRE, BinarySensorDeviceClass.SMOKE),
    "4": ("power_supply", ZoneType.TECHNICAL, BinarySensorDeviceClass.POWER),
}


@pytest.mark.parametrize("zone_data", ZONE_DEFINITIONS)
async def test_binary_sensor_setup(
    hass: HomeAssistant, mock_config, mock_client, zone_data
) -> None:
    """Test binary sensor setup."""
    entity_id = f"binary_sensor.{zone_data.name.lower().replace(' ', '_')}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == zone_data.name
    assert state.state == "off"


async def test_binary_sensor_update(
    hass: HomeAssistant, mock_config, mock_zone
) -> None:
    """Test binary sensor updates."""
    entity_id = "binary_sensor.entrance"

    # Test open state
    type(mock_zone).input = PropertyMock(return_value=ZoneInput.OPEN)
    dispatcher.async_dispatcher_send(hass, SIGNAL_UPDATE_SENSOR.format(mock_zone.id))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"

    # Test closed state
    type(mock_zone).input = PropertyMock(return_value=ZoneInput.CLOSED)
    dispatcher.async_dispatcher_send(hass, SIGNAL_UPDATE_SENSOR.format(mock_zone.id))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"
