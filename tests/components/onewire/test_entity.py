"""Tests for 1-Wire device family 28 (DS18B20)."""
from os import path
from unittest.mock import mock_open, patch

from homeassistant.components.onewire.const import DEFAULT_SYSBUS_MOUNT_DIR
from homeassistant.components.onewire.sensor import OneWireDirect

DEVICE_ID = "28.111111111111"
DEVICE_NAME = "My DS18B20"


def get_onewiredirect_sensor() -> OneWireDirect:
    """Initialise a onewiredirect sensor."""
    device_id = DEVICE_ID.replace(".", "-")
    init_args = [
        DEVICE_NAME,
        path.join(DEFAULT_SYSBUS_MOUNT_DIR, device_id, "w1_slave"),
        "temperature",
    ]
    return OneWireDirect(*init_args)


def test_onewiredirect_update(hass):
    """Test that onewiredirect updates correctly."""
    test_sensor = get_onewiredirect_sensor()

    # test standard update
    mo_main = mock_open(read_data=": crc=09 YES\nt=25123")
    with patch(
        "homeassistant.components.onewire.sensor.open",
        mo_main,
    ):
        test_sensor.update()
        assert test_sensor.state == 25.1


def test_onewiredirect_update_slow_value(hass):
    """Test that onewiredirect updates correctly after 4 bad value."""
    test_sensor = get_onewiredirect_sensor()

    mo_main = mock_open()
    mo_main.side_effect = [
        mock_open(read_data=": crc=NO").return_value,
        mock_open(read_data=": crc=NO").return_value,
        mock_open(read_data=": crc=NO").return_value,
        mock_open(read_data=": crc=NO").return_value,
        mock_open(read_data=": crc=09 YES\nt=25723").return_value,
    ]
    with patch(
        "homeassistant.components.onewire.sensor.open",
        mo_main,
    ):
        test_sensor.update()
        assert test_sensor.state == 25.7


def test_onewiredirect_update_very_slow_value(hass):
    """Test that onewiredirect update fails after 5 bad value."""
    test_sensor = get_onewiredirect_sensor()

    mo_main = mock_open()
    mo_main.side_effect = [
        mock_open(read_data=": crc=NO").return_value,
        mock_open(read_data=": crc=NO").return_value,
        mock_open(read_data=": crc=NO").return_value,
        mock_open(read_data=": crc=NO").return_value,
        mock_open(read_data=": crc=NO").return_value,
        mock_open(read_data=": crc=09 YES\nt=25723").return_value,
    ]
    with patch(
        "homeassistant.components.onewire.sensor.open",
        mo_main,
    ):
        test_sensor.update()
        assert test_sensor.state is None


def test_onewiredirect_update_no_value(hass):
    """Test that onewiredirect behaves correctly after missing value."""
    test_sensor = get_onewiredirect_sensor()

    mo_main = mock_open(read_data="")
    with patch(
        "homeassistant.components.onewire.sensor.open",
        mo_main,
    ):
        test_sensor.update()
        assert test_sensor.state is None


def test_onewiredirect_update_disconnected(hass):
    """Test that onewiredirect behaves correctly after device has disconnected."""
    test_sensor = get_onewiredirect_sensor()

    mo_main = mock_open()
    mo_main.side_effect = FileNotFoundError
    with patch(
        "homeassistant.components.onewire.sensor.open",
        mo_main,
    ):
        test_sensor.update()
        assert test_sensor.state is None
