"""The test for the NuHeat thermostat module."""
from unittest.mock import MagicMock, Mock

from homeassistant.const import CONF_DEVICE, CONF_PASSWORD, CONF_USERNAME

MOCK_DEVICE_ID = "12345"
MOCK_DEVICE_NAME = "IT500 Salus"

MOCK_CONFIG_ENTRY = {
    CONF_USERNAME: "test@salus.com",
    CONF_PASSWORD: "salusPassword",
    CONF_DEVICE: MOCK_DEVICE_ID,
}


def _get_mock_device():
    mock_device = Mock(
        device_id=MOCK_DEVICE_ID,
    )
    mock_device.name = MOCK_DEVICE_NAME
    return mock_device


def _get_mock_device_reading():
    return Mock(
        current_temperature=21.5,
        current_target_temperature=23.5,
        heat_on=True,
    )


def _get_mock_device_reading_not_heating():
    return Mock(
        current_temperature=23,
        current_target_temperature=22.5,
        heat_on=False,
    )


def _get_mock_salus(get_mock_device_reading=_get_mock_device_reading):
    salus_mock = MagicMock()
    type(salus_mock).login = MagicMock()
    type(salus_mock).get_devices = MagicMock(return_value=[_get_mock_device()])
    type(salus_mock).get_device_reading = MagicMock(
        return_value=get_mock_device_reading()
    )

    return salus_mock
