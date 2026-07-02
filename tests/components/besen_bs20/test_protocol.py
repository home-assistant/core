"""Tests for the Besen BS20 packet protocol."""

from besen_bs20.exceptions import ProtocolError
from besen_bs20.protocol import (
    PacketAssembler,
    build_command,
    bytes_to_int_little,
    bytes_to_integer,
    bytes_to_long_little,
    bytes_to_timestamp,
    bytes_to_timezoned_epoch,
    charging_status,
    device_name_bytes,
    generate_charge_id,
    get_phases,
    key_by_value,
    parse_charge_start,
    parse_charge_stop,
    parse_login,
    parse_name,
    parse_output_amps,
    parse_packet,
    parse_single_ac_status,
    parse_system_language,
    parse_system_time,
    parse_temperature_unit,
    parse_version,
    safe_decode,
    timestamp_bytes,
)
import pytest


def test_build_and_parse_command() -> None:
    """Command packets include framing, password, command, and checksum."""

    packet = build_command(12345678, "123456", 32770)

    parsed = parse_packet(packet)

    assert parsed.password == b"123456"
    assert parsed.command == 32770
    assert parsed.data == b""
    assert parsed.raw == packet


def test_parse_rejects_bad_checksum() -> None:
    """Checksum mismatches are rejected."""

    packet = bytearray(build_command(12345678, "123456", 32770))
    packet[10] ^= 0xFF

    with pytest.raises(ProtocolError, match="checksum"):
        parse_packet(packet)


@pytest.mark.parametrize(
    ("packet", "match"),
    [
        (b"\x06\x01", "shorter"),
        (b"\x00" * 25, "header"),
        (bytes(bytearray(build_command(12345678, "123456", 32770))[:24]), "shorter"),
    ],
)
def test_parse_rejects_invalid_framing(packet: bytes, match: str) -> None:
    """Malformed packets are rejected before parsing."""

    with pytest.raises(ProtocolError, match=match):
        parse_packet(packet)


def test_parse_rejects_length_and_footer_errors() -> None:
    """Length and footer validation errors are reported."""

    bad_length = bytearray(build_command(12345678, "123456", 32770))
    bad_length[3] += 1
    with pytest.raises(ProtocolError, match="length"):
        parse_packet(bad_length)

    bad_footer = bytearray(build_command(12345678, "123456", 32770))
    bad_footer[-1] = 0
    with pytest.raises(ProtocolError, match="footer"):
        parse_packet(bad_footer)


def test_build_command_validates_payload_and_accepts_hex_serial() -> None:
    """Command building validates byte ranges and hex serial strings."""

    packet = build_command("00BC614E", "123456", 32770, [[1, 2], 3])

    assert parse_packet(packet).data == b"\x01\x02\x03"
    with pytest.raises(ProtocolError, match="outside"):
        build_command(12345678, "123456", 32770, [256])


def test_packet_assembler_reassembles_fragmented_notifications() -> None:
    """BLE notification fragments are reassembled into full packets."""

    packet = build_command(12345678, "123456", 32771, [1])
    assembler = PacketAssembler()

    assert assembler.feed(packet[:7]) == []
    assert assembler.feed(packet[7:15]) == []
    packets = assembler.feed(packet[15:])

    assert len(packets) == 1
    assert packets[0].command == 32771
    assert packets[0].data == b"\x01"


def test_packet_assembler_discards_noise_and_invalid_lengths() -> None:
    """Assembler skips noise and impossible packet lengths."""

    packet = build_command(12345678, "123456", 32771, [1])
    invalid_length = bytearray(b"\x06\x01\x00\x05")
    assembler = PacketAssembler()

    assert assembler.feed(b"noise") == []
    assert assembler.feed(invalid_length) == []
    packets = assembler.feed(packet)

    assert len(packets) == 1
    assert packets[0].command == 32771


def test_parse_login_response() -> None:
    """Login parser extracts charger identity and phase count."""

    data = bytearray(69)
    data[0] = 10
    data[1:16] = b"Besen\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    data[17:32] = b"BS20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    data[33:49] = b"HW1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    data[49:53] = bytes([0, 0, 0, 22])
    data[53] = 32
    data[54:69] = b"basic\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    info = parse_login(bytes(data), "12345678")

    assert info["serial"] == "12345678"
    assert info["phases"] == 3
    assert info["manufacturer"] == "Besen"
    assert info["model"] == "BS20"
    assert info["hardware_version"] == "HW1"
    assert info["output_power"] == 22
    assert info["output_max_amps"] == 32


def test_parse_single_ac_status_three_phase() -> None:
    """AC status parser extracts electrical values and charger state."""

    data = bytearray(34)
    data[0] = 1
    data[1:3] = (2300).to_bytes(2, "big")
    data[3:5] = (1600).to_bytes(2, "big")
    data[5:9] = bytes([0, 0, 0, 42])
    data[9:13] = (1234).to_bytes(4, "big")
    data[13:15] = (22500).to_bytes(2, "big")
    data[15:17] = (23000).to_bytes(2, "big")
    data[18] = 4
    data[19] = 1
    data[20] = 14
    data[21:25] = b"\x00\x00\x00\x00"
    data[25:27] = (2310).to_bytes(2, "big")
    data[27:29] = (1000).to_bytes(2, "big")
    data[29:31] = (2320).to_bytes(2, "big")
    data[31:33] = (900).to_bytes(2, "big")

    status = parse_single_ac_status(bytes(data), "12345678")

    assert status["l1_voltage"] == 230.0
    assert status["l1_amperage"] == 16.0
    assert status["inner_temp_c"] == 25.0
    assert status["outer_temp"] == 30.0
    assert status["plug_state"] == "Connected Locked"
    assert status["output_state"] == "Charging"
    assert status["current_state"] == "Completed"
    assert status["charging_status"] == "Finish Charging"
    assert status["charger_status"] is True
    assert status["l2_voltage"] == 231.0
    assert status["l3_amperage"] == 9.0
    assert status["current_energy"] == 8078


def test_parse_single_ac_status_handles_short_unknown_values() -> None:
    """Status parser handles short packets and unknown enum indexes."""

    data = bytearray(24)
    data[0] = 1
    data[1:3] = (2300).to_bytes(2, "big")
    data[3:5] = (0).to_bytes(2, "big")
    data[9:13] = (100).to_bytes(4, "big")
    data[13:15] = (255).to_bytes(2, "big")
    data[15:17] = (255).to_bytes(2, "big")
    data[18] = 99
    data[19] = 99
    data[20] = 99
    data[21:23] = b"\x00\x01"

    status = parse_single_ac_status(bytes(data), "12345678")

    assert status["inner_temp_c"] == -1.0
    assert status["outer_temp"] == -1.0
    assert status["plug_state"] == "Unknown 99"
    assert status["output_state"] == "Unknown 99"
    assert status["current_state"] == "Unknown 99"
    assert status["new_protocol"] is False
    assert status["current_energy"] == 0


def test_device_name_bytes_are_prefixed_and_padded() -> None:
    """Device names are ACP-prefixed and padded to the expected length."""

    payload = device_name_bytes("Garage")

    assert bytes(payload[:10]) == b"ACP#Garage"
    assert len(payload) == 32
    assert payload[-1] == 0


def test_protocol_scalar_helpers() -> None:
    """Scalar helpers convert wire formats."""

    assert bytes_to_integer(b"\x01\x00", "little") == 1
    assert bytes_to_int_little(b"\x01\x02\x03\x04") == 0x01020304
    assert bytes_to_int_little(b"\x01") == 0
    assert bytes_to_long_little(b"\xff\xff\xff\xff") == 0xFFFFFFFF
    assert get_phases(10) == 3
    assert get_phases(1) == 1
    assert safe_decode(b"Garage\x00\x00") == "Garage"
    assert len(timestamp_bytes()) == 4
    assert len(generate_charge_id()) == 16
    assert bytes_to_timestamp(0)
    assert isinstance(bytes_to_timezoned_epoch(0), int)


@pytest.mark.parametrize(
    ("plug_state", "current_state", "expected"),
    [
        (None, 1, None),
        (1, None, None),
        (1, 1, 8),
        (1, 2, 11),
        (1, 10, 9),
        (1, 11, 10),
        (1, 12, 7),
        (1, 13, 1),
        (4, 14, 2),
        (2, 14, 3),
        (4, 15, 4),
        (1, 17, 5),
        (1, 20, 6),
        (1, 99, None),
    ],
)
def test_charging_status_mapping(
    plug_state: int | None,
    current_state: int | None,
    expected: int | None,
) -> None:
    """Charging status maps plug/current states."""

    assert charging_status(plug_state, current_state) == expected


def test_config_and_command_parsers() -> None:
    """Config and command response parsers return expected dictionaries."""

    version_data = bytearray(36)
    version_data[0:15] = b"HW2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    version_data[16:31] = b"SW2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    version_data[32:36] = b"\x00\x00\x00\x05"

    name_data = bytearray(32)
    name_data[1:8] = b"Garage\x00"

    time_data = bytearray(5)
    time_data[1:5] = b"\x00\x00\x00\x01"

    assert parse_version(bytes(version_data), "")["software_version"] == "SW2"
    assert parse_output_amps(b"\x02\x10", "") == {"charge_amps": 16}
    assert parse_name(bytes(name_data), "") == {"device_name": "Garage"}
    assert parse_system_time(bytes(time_data), "")["system_time_raw"] == (
        bytes_to_timezoned_epoch(1)
    )
    assert parse_system_language(b"\x02\x03", "") == {"language": "Deutsch"}
    assert parse_system_language(b"\x02\xff", "") == {"language": None}
    assert parse_temperature_unit(b"\x02\x01", "") == {"temperature_unit": "Celsius"}
    assert parse_temperature_unit(b"\x02\x02", "") == {"temperature_unit": "Fahrenheit"}
    assert parse_charge_start(b"\x01\x00\x01\x00\x10", "") == {
        "line_id": 1,
        "reservation_result": "No error",
        "start_result": 1,
        "error_reason": "No error",
        "output_amps": 16,
    }
    assert parse_charge_stop(b"\x01\x0b\x00", "") == {
        "line_id": 1,
        "stop_result": "App stop",
        "error_reason": 0,
    }
    assert key_by_value({"a": 1}, 2) is None


def test_device_name_bytes_truncates_long_names() -> None:
    """Long device names are truncated to the protocol field size."""

    payload = device_name_bytes("VeryLongGarageName")

    assert bytes(payload[:15]) == b"ACP#VeryLongGar"
    assert len(payload) == 32
