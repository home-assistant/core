"""Test Z-Wave Services."""
from .common import setup_ozw


async def test_services(hass, lock_data, sent_messages, lock_msg, caplog):
    """Test services on lock."""
    await setup_ozw(hass, fixture=lock_data)

    # Test set_config_parameter list by label
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 10, "parameter": 1, "value": "Disabled"},
        blocking=True,
    )
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 281475154706452}

    # Test set_config_parameter list by index int
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 10, "parameter": 1, "value": 0},
        blocking=True,
    )
    assert len(sent_messages) == 2
    msg = sent_messages[1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 281475154706452}

    # Test set_config_parameter int
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 10, "parameter": 6, "value": 0},
        blocking=True,
    )
    assert len(sent_messages) == 3
    msg = sent_messages[2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 1688850038259731}

    # Test set_config_parameter invalid list int
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 10, "parameter": 1, "value": 12},
        blocking=True,
    )
    assert len(sent_messages) == 3
    assert "Value 12 out of range for parameter 1" in caplog.text

    # Test set_config_parameter invalid list string
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 10, "parameter": 1, "value": "Blah"},
        blocking=True,
    )
    assert len(sent_messages) == 3
    assert "Invalid value Blah for parameter 1" in caplog.text

    # Test set_config_parameter int out of range
    await hass.services.async_call(
        "ozw",
        "set_config_parameter",
        {"node_id": 10, "parameter": 6, "value": 2147483657},
        blocking=True,
    )
    assert len(sent_messages) == 3
    assert "Value 12 out of range for parameter 1" in caplog.text
