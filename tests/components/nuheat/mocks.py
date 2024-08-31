"""The test for the NuHeat thermostat module."""

from unittest.mock import MagicMock, Mock

from nuheat.config import SCHEDULE_HOLD, SCHEDULE_RUN, SCHEDULE_TEMPORARY_HOLD

from homeassistant.components.nuheat.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME

MOCK_CONFIG_ENTRY = {
    CONF_USERNAME: "me",
    CONF_PASSWORD: "secret",
    CONF_SERIAL_NUMBER: 12345,
}


def _get_mock_thermostat_run():
    serial_number = "12345"
    thermostat = Mock(
        serial_number=serial_number,
        room="Master bathroom",
        online=True,
        heating=True,
        temperature=2222,
        celsius=22,
        fahrenheit=72,
        max_celsius=69,
        max_fahrenheit=157,
        min_celsius=5,
        min_fahrenheit=41,
        schedule_mode=SCHEDULE_RUN,
        target_celsius=22,
        target_fahrenheit=72,
        target_temperature=2217,
    )

    thermostat.get_data = Mock()
    thermostat.resume_schedule = Mock()
    thermostat.schedule_mode = Mock()
    return thermostat


def _get_mock_thermostat_schedule_hold_unavailable():
    serial_number = "876"
    thermostat = Mock(
        serial_number=serial_number,
        room="Guest bathroom",
        online=False,
        heating=False,
        temperature=12,
        celsius=12,
        fahrenheit=102,
        max_celsius=99,
        max_fahrenheit=357,
        min_celsius=9,
        min_fahrenheit=21,
        schedule_mode=SCHEDULE_HOLD,
        target_celsius=23,
        target_fahrenheit=79,
        target_temperature=2609,
    )

    thermostat.get_data = Mock()
    thermostat.resume_schedule = Mock()
    thermostat.schedule_mode = Mock()
    return thermostat


def _get_mock_thermostat_schedule_hold_available():
    serial_number = "876"
    thermostat = Mock(
        serial_number=serial_number,
        room="Available bathroom",
        online=True,
        heating=False,
        temperature=12,
        celsius=12,
        fahrenheit=102,
        max_celsius=99,
        max_fahrenheit=357,
        min_celsius=9,
        min_fahrenheit=21,
        schedule_mode=SCHEDULE_HOLD,
        target_celsius=23,
        target_fahrenheit=79,
        target_temperature=2609,
    )

    thermostat.get_data = Mock()
    thermostat.resume_schedule = Mock()
    thermostat.schedule_mode = Mock()
    return thermostat


def _get_mock_thermostat_schedule_temporary_hold():
    serial_number = "999"
    thermostat = Mock(
        serial_number=serial_number,
        room="Temp bathroom",
        online=True,
        heating=False,
        temperature=14,
        celsius=13,
        fahrenheit=202,
        max_celsius=39,
        max_fahrenheit=357,
        min_celsius=3,
        min_fahrenheit=31,
        schedule_mode=SCHEDULE_TEMPORARY_HOLD,
        target_celsius=43,
        target_fahrenheit=99,
        target_temperature=3729,
        max_temperature=5000,
        min_temperature=1,
    )

    thermostat.get_data = Mock()
    thermostat.resume_schedule = Mock()
    thermostat.schedule_mode = Mock()
    return thermostat


def _get_mock_nuheat(authenticate=None, get_thermostat=None):
    nuheat_mock = MagicMock()
    type(nuheat_mock).authenticate = MagicMock()
    type(nuheat_mock).get_thermostat = MagicMock(return_value=get_thermostat)

    return nuheat_mock


def _mock_get_config():
    """Return a default nuheat config."""
    return {
        DOMAIN: {CONF_USERNAME: "me", CONF_PASSWORD: "secret", CONF_DEVICES: [12345]}
    }
