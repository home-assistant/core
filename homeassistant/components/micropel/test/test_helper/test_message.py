"""Tests of building and parsing messages for PLCs."""
from ...helper.message import Message


def test_build_message():
    """Test of message building."""
    expected_message = "*160220#55"
    message = Message.build_message(None, "*", 0x16, "0220")
    assert message == expected_message

    expected_message = "*0361646D696E64617400#5E"
    message = Message.build_message(None, "*", 0x03, "61646D696E64617400")
    assert message == expected_message

    expected_message = "*16022012345678#F9"
    message = Message.build_message(None, "*", 0x16, "022012345678")
    assert message == expected_message

    expected_message = "@01*16022012345678#9A"
    message = Message.build_message(1, "*", 0x16, "022012345678")
    assert message == expected_message

    expected_message = "*03#8D"
    message = Message.build_message(None, "*", 0x03, None)
    assert message == expected_message


def test_get_crc():
    """Test of CRC."""
    expected_result = "55"
    result = Message.get_crc("*160220#55")
    assert result == expected_result

    expected_result = "5E"
    result = Message.get_crc("*0361646D696E64617400#5E")
    assert result == expected_result

    expected_result = "F9"
    result = Message.get_crc("*16022012345678#F9")
    assert result == expected_result

    expected_result = "9A"
    result = Message.get_crc("@01*16022012345678#9A")
    assert result == expected_result

    expected_result = "8D"
    result = Message.get_crc("*03#8D")
    assert result == expected_result


def test_get_plc_address():
    """Test of PLC address parsing."""
    expected_result = None
    result = Message.get_plc_address("*160220#55")
    assert result == expected_result

    expected_result = "01"
    result = Message.get_plc_address("@01*16022012345678#9A")
    assert result == expected_result


def test_get_cmd_id():
    """Test of parsing CMD ID."""
    expected_result = "16"
    result = Message.get_cmd_id("*160220#55")
    assert result == expected_result

    expected_result = "03"
    result = Message.get_cmd_id("*0361646D696E64617400#5E")
    assert result == expected_result

    expected_result = "16"
    result = Message.get_cmd_id("!16022035#84")
    assert result == expected_result

    expected_result = "16"
    result = Message.get_cmd_id("@01*16022012345678#9A")
    assert result == expected_result

    expected_result = "16"
    result = Message.get_cmd_id("@01!16022035#84")
    assert result == expected_result

    expected_result = "03"
    result = Message.get_cmd_id("*03#8D")
    assert result == expected_result


def test_get_cmd_type():
    """Test of parsing CMD type."""
    expected_result = "*"
    result = Message.get_cmd_type("*160220#55")
    assert result == expected_result

    expected_result = "*"
    result = Message.get_cmd_type("*0361646D696E64617400#5E")
    assert result == expected_result

    expected_result = "!"
    result = Message.get_cmd_type("!16022035#84")
    assert result == expected_result

    expected_result = "*"
    result = Message.get_cmd_type("@01*16022012345678#9A")
    assert result == expected_result

    expected_result = "!"
    result = Message.get_cmd_type("@01!16022035#84")
    assert result == expected_result

    expected_result = "*"
    result = Message.get_cmd_type("*03#8D")
    assert result == expected_result


def test_get_data():
    """Test of parsing data from message."""
    expected_result = "0220"
    result = Message.get_data("*160220#55")
    assert result == expected_result

    expected_result = "61646D696E64617400"
    result = Message.get_data("*0361646D696E64617400#5E")
    assert result == expected_result

    expected_result = "022012345678"
    result = Message.get_data("*16022012345678#F9")
    assert result == expected_result

    expected_result = "022012345678"
    result = Message.get_data("@01*16022012345678#9A")
    assert result == expected_result

    expected_result = "022035"
    result = Message.get_data("!16022035#84")
    assert result == expected_result

    expected_result = "022035"
    result = Message.get_data("@02!16022035#84")
    assert result == expected_result

    expected_result = None
    result = Message.get_data("*03#8D")
    assert result == expected_result
