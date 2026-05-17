"""Test AirTouch 3 response parsing."""

import logging

import pytest

from homeassistant.components.airtouch3.comms.enums import AcMode
from homeassistant.components.airtouch3.comms.message_constants import MessageConstants
from homeassistant.components.airtouch3.comms.message_response_parser import (
    MessageResponseParser,
)

AVAILABLE_FLAG = 0x80
RESPONSE_LENGTH = 520
SYSTEM_ID = "35901813"


def _make_response(num_zones: int) -> bytearray:
    """Create a minimal AirTouch response buffer."""
    response = bytearray(RESPONSE_LENGTH)
    response[MessageConstants.NUMBER_OF_ZONES] = num_zones
    response[MessageConstants.AIRCON_STATUS] = AVAILABLE_FLAG
    response[
        MessageConstants.AIRTOUCH_ID_START : MessageConstants.AIRTOUCH_ID_START
        + MessageConstants.AIRTOUCH_ID_LENGTH
    ] = SYSTEM_ID.encode()

    for index in range(num_zones):
        response[MessageConstants.GROUP_DATA_START + index] = index << 4
        response[MessageConstants.ZONE_DATA_START + index] = AVAILABLE_FLAG
        response[MessageConstants.GROUP_SETTING_START + index] = 20

        name = f"Zone {index + 1}".encode()
        start = MessageConstants.GROUP_NAME_START + index * 8
        response[start : start + len(name)] = name

    return response


def test_parse_assigns_touchpad_temperature_to_configured_zone() -> None:
    """Test touchpad temperature is mapped to its protocol group id."""
    response = _make_response(4)
    response[MessageConstants.SENSOR_DATA_START] = AVAILABLE_FLAG | 20
    response[MessageConstants.SENSOR_DATA_START + 2] = AVAILABLE_FLAG | 22
    response[MessageConstants.TOUCHPAD_GROUP_ID] = 4
    response[MessageConstants.TOUCHPAD_TEMPERATURE] = AVAILABLE_FLAG | 24

    aircon = MessageResponseParser(response, logging.getLogger(__name__)).parse()

    assert aircon.system_id == SYSTEM_ID
    assert aircon.zones[0].sensor
    assert aircon.zones[0].sensor.current_temperature == 20
    assert aircon.zones[1].sensor is None
    assert aircon.zones[2].sensor
    assert aircon.zones[2].sensor.current_temperature == 22
    assert aircon.zones[3].sensor
    assert aircon.zones[3].sensor.current_temperature == 24
    assert aircon.room_temperature == 22


@pytest.mark.parametrize(
    ("raw_mode", "expected_mode"),
    [
        (0, AcMode.AUTO),
        (1, AcMode.HEAT),
        (2, AcMode.DRY),
        (3, AcMode.FAN),
        (4, AcMode.COOL),
    ],
)
def test_parse_ac_mode(raw_mode: int, expected_mode: AcMode) -> None:
    """Test AirTouch AC modes are mapped correctly."""
    response = _make_response(1)
    response[MessageConstants.AIRCON_MODE] = raw_mode

    aircon = MessageResponseParser(response, logging.getLogger(__name__)).parse()

    assert aircon.mode == expected_mode


def test_parse_short_response_raises() -> None:
    """Test short AirTouch responses fail before fixed offsets are read."""
    response = bytearray(
        MessageConstants.AIRTOUCH_ID_START + MessageConstants.AIRTOUCH_ID_LENGTH - 1
    )

    with pytest.raises(ValueError):
        MessageResponseParser(response, logging.getLogger(__name__)).parse()


def test_parse_unsupported_zone_count_raises() -> None:
    """Test unsupported AirTouch zone counts fail before zone parsing."""
    response = _make_response(1)
    response[MessageConstants.NUMBER_OF_ZONES] = 17

    with pytest.raises(ValueError):
        MessageResponseParser(response, logging.getLogger(__name__)).parse()
