"""Aussie Broadband sensor platform tests."""
from unittest.mock import patch

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

from .common import setup_platform

MOCK_USAGE = {
    "usedMb": 54321,
    "downloadedMb": 50000,
    "uploadedMb": 4321,
    "daysTotal": 28,
    "daysRemaining": 25,
}


@patch("aussiebb.AussieBB.get_usage", return_value=MOCK_USAGE)
async def test_sensor_states(mock_get_services, hass):
    """Tests that the sensors are correct."""
    await setup_platform(hass, SENSOR_DOMAIN)

    assert hass.states.get("sensor.total_usage").state == "54321"
    assert hass.states.get("sensor.downloaded").state == "50000"
    assert hass.states.get("sensor.uploaded").state == "4321"
    assert hass.states.get("sensor.billing_cycle_length").state == "28"
    assert hass.states.get("sensor.billing_cycle_remaining").state == "25"
