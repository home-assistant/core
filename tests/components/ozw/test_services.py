"""Test Z-Wave Services."""
from openzwavemqtt.const import ATTR_POSITION, ATTR_VALUE
from openzwavemqtt.exceptions import InvalidValueError, NotFoundError, WrongTypeError
import pytest

from .common import setup_ozw


async def test_services(hass, light_data, sent_messages):
    """Test services on lock."""
    await setup_ozw(hass, fixture=light_data)

    # Test set_config_parameter list by label
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 39, "parameter": 1, "value": "Disable"},
        blocking=True,
    )
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 281475641245716}

    # Test set_config_parameter list by index int
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 39, "parameter": 1, "value": 1},
        blocking=True,
    )
    assert len(sent_messages) == 2
    msg = sent_messages[1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 1, "ValueIDKey": 281475641245716}

    # Test set_config_parameter int
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 39, "parameter": 3, "value": 55},
        blocking=True,
    )
    assert len(sent_messages) == 3
    msg = sent_messages[2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 55, "ValueIDKey": 844425594667027}

    # Test set_config_parameter invalid list int
    with pytest.raises(NotFoundError):
        assert await hass.services.async_call(
            "ozw",
            "set_config_parameter",
            {"node_id": 39, "parameter": 1, "value": 12},
            blocking=True,
        )
    assert len(sent_messages) == 3

    # Test set_config_parameter invalid list value
    with pytest.raises(NotFoundError):
        assert await hass.services.async_call(
            "ozw",
            "set_config_parameter",
            {"node_id": 39, "parameter": 1, "value": "Blah"},
            blocking=True,
        )
    assert len(sent_messages) == 3

    # Test set_config_parameter invalid list value type
    with pytest.raises(WrongTypeError):
        assert await hass.services.async_call(
            "ozw",
            "set_config_parameter",
            {
                "node_id": 39,
                "parameter": 1,
                "value": {ATTR_VALUE: True, ATTR_POSITION: 1},
            },
            blocking=True,
        )
    assert len(sent_messages) == 3

    # Test set_config_parameter int out of range
    with pytest.raises(InvalidValueError):
        assert await hass.services.async_call(
            "ozw",
            "set_config_parameter",
            {"node_id": 39, "parameter": 3, "value": 2147483657},
            blocking=True,
        )
    assert len(sent_messages) == 3

    # Test set_config_parameter short
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 39, "parameter": 81, "value": 3000},
        blocking=True,
    )
    assert len(sent_messages) == 4
    msg = sent_messages[3]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 3000, "ValueIDKey": 22799473778098198}

    # Test set_config_parameter byte
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 39, "parameter": 16, "value": 20},
        blocking=True,
    )
    assert len(sent_messages) == 5
    msg = sent_messages[4]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 20, "ValueIDKey": 4503600291905553}
