"""Tests for the ness_alarm binary sensor component."""

from homeassistant.components.binary_sensor.ness_alarm import (
    NessZoneBinarySensor)
from homeassistant.components.ness_alarm import (
    ZoneChangedData)


async def test_handle_zone_change(hass):
    """Test zone change event handling."""
    sensor = NessZoneBinarySensor(zone_id=1, name='Zone 1', zone_type='motion')
    sensor.hass = hass

    assert sensor.is_on is False
    sensor._handle_zone_change(ZoneChangedData(zone_id=1, state=True))
    assert sensor.is_on is True


async def test_handle_zone_change_different_zone(hass):
    """Test zone change event handling for a different zone."""
    sensor = NessZoneBinarySensor(zone_id=1, name='Zone 1', zone_type='motion')
    sensor.hass = hass

    assert sensor.is_on is False
    sensor._handle_zone_change(ZoneChangedData(zone_id=2, state=True))
    assert sensor.is_on is False
