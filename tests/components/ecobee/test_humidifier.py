"""The test for the ecobee thermostat humidifier module."""
from unittest import mock

import pytest

from homeassistant.components.ecobee import humidifier as ecobee
from homeassistant.components.humidifier.const import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DEVICE_CLASS_HUMIDIFIER,
    MODE_AUTO,
    SUPPORT_MODES,
)

from .common import data_fixture, ecobee_fixture

__all__ = ["data_fixture", "ecobee_fixture"]

MODE_MANUAL = "manual"
MODE_OFF = "off"


@pytest.fixture(name="humidifier")
def humidifier_fixture(data):
    """Set up ecobee thermostat object."""
    return ecobee.EcobeeHumidifier(data, 1)


async def test_attributes(humidifier):
    """Test the attributes within the humidifier entity."""
    assert humidifier.is_on is False
    assert humidifier.max_humidity == DEFAULT_MAX_HUMIDITY
    assert humidifier.min_humidity == DEFAULT_MIN_HUMIDITY
    assert humidifier.humidity == 15
    assert humidifier.available_modes == [
        MODE_OFF,
        MODE_AUTO,
        MODE_MANUAL,
    ]
    assert humidifier.name == "Ecobee"
    assert humidifier.device_class == DEVICE_CLASS_HUMIDIFIER
    assert humidifier.mode == "off"
    assert humidifier.supported_features == SUPPORT_MODES
    assert humidifier.target_humidity == 45


async def test_turn_on(humidifier, data):
    """Test turning on humidifier."""
    data.reset_mock()
    humidifier.turn_on()
    data.ecobee.set_humidifier_mode.assert_has_calls([mock.call(1, "manual")])


async def test_turn_off(humidifier, data):
    """Test turning off humidifier."""
    data.reset_mock()
    humidifier.turn_off()
    data.ecobee.set_humidifier_mode.assert_has_calls([mock.call(1, "off")])


async def test_set_mode(humidifier, data):
    """Test setting each humidifier mode."""
    data.reset_mock()
    """ Auto """
    humidifier.set_mode("auto")
    data.ecobee.set_humidifier_mode.assert_has_calls([mock.call(1, "auto")])
    """ Off """
    humidifier.set_mode("off")
    data.ecobee.set_humidifier_mode.assert_has_calls([mock.call(1, "off")])
    """ Manual """
    humidifier.set_mode("manual")
    data.ecobee.set_humidifier_mode.assert_has_calls([mock.call(1, "manual")])


async def test_set_humidity(humidifier, data):
    """Test setting desired humidity."""
    data.reset_mock()
    humidifier.set_humidity("40")
    data.ecobee.set_humidity.assert_has_calls([mock.call(1, "40")])
