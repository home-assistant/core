"""Tests for the Envisalink zone binary sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_LAST_TRIP_TIME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import ZONE_ENTITY, setup_envisalink

# The library reports last_fault in seconds, capped at 327680 (65536 five-second
# ticks); at or above the cap the real value is unknown.
LAST_FAULT_MAX_SECONDS = 65536 * 5


async def test_zone_is_on(hass: HomeAssistant, mock_controller: MagicMock) -> None:
    """Test the zone reflects its open status on a zone update."""
    assert await setup_envisalink(hass)
    assert hass.states.get(ZONE_ENTITY).state == STATE_OFF

    mock_controller.alarm_state["zone"][1]["status"]["open"] = True
    mock_controller.callback_zone_state_change(1)
    await hass.async_block_till_done()

    assert hass.states.get(ZONE_ENTITY).state == STATE_ON


async def test_zone_attributes(
    hass: HomeAssistant, mock_controller: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the zone exposes device class, zone number, and last trip time."""
    freezer.move_to("2026-01-01 12:00:00+00:00")
    # last_fault is the number of seconds since the fault; it is subtracted
    # from the current (second-accurate) time to get the last trip time.
    mock_controller.alarm_state["zone"][1]["last_fault"] = 300
    assert await setup_envisalink(hass)

    attrs = hass.states.get(ZONE_ENTITY).attributes
    assert attrs[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR
    assert attrs["zone"] == 1
    expected = dt_util.now().replace(microsecond=0) - timedelta(seconds=300)
    assert attrs[ATTR_LAST_TRIP_TIME] == expected.isoformat()


async def test_zone_last_trip_time_unknown_at_max(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test last trip time is None once the library caps the fault counter."""
    mock_controller.alarm_state["zone"][1]["last_fault"] = LAST_FAULT_MAX_SECONDS
    assert await setup_envisalink(hass)

    assert hass.states.get(ZONE_ENTITY).attributes[ATTR_LAST_TRIP_TIME] is None


async def test_zone_update_filtering(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test zone updates are filtered by number; None applies to all."""
    assert await setup_envisalink(hass)
    zone_status = mock_controller.alarm_state["zone"][1]["status"]
    zone_status["open"] = True

    # Update for a different zone (int) is ignored.
    mock_controller.callback_zone_state_change(2)
    await hass.async_block_till_done()
    assert hass.states.get(ZONE_ENTITY).state == STATE_OFF

    # A matching zone delivered as a string is coerced and applies.
    mock_controller.callback_zone_state_change("1")
    await hass.async_block_till_done()
    assert hass.states.get(ZONE_ENTITY).state == STATE_ON

    # A None zone applies to every entity.
    zone_status["open"] = False
    mock_controller.callback_zone_state_change(None)
    await hass.async_block_till_done()
    assert hass.states.get(ZONE_ENTITY).state == STATE_OFF
