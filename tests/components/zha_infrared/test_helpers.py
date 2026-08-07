"""Tests for ZHA Infrared helpers."""

from homeassistant.components.zha_infrared.codecs import decode_received_payload
from homeassistant.components.zha_infrared.codecs.pronto import (
    decode_pronto_hex_to_raw_timings,
    encode_raw_to_pronto_hex,
)
from homeassistant.components.zha_infrared.codecs.tuya import encode_raw_to_tuya_base64
from homeassistant.components.zha_infrared.helpers import _parse_profile


def test_encode_raw_to_tuya_base64_saturates_and_encodes() -> None:
    """Test raw timing conversion to TS1201 base64 payload."""
    assert encode_raw_to_tuya_base64([100, -200, 70000]) == "ZADIAP//"


def test_decode_received_payload_decodes_tuya_base64() -> None:
    """Decode TS1201 base64 payload into alternating signed timings."""
    timings = decode_received_payload("tuya_base64_rawtimings_v1", "ZADIAP//")
    assert timings == [100, -200, 65535]


def test_encode_raw_to_pronto_hex_format() -> None:
    """Encode timings into Xiaomi-compatible Pronto Hex representation."""
    pronto = encode_raw_to_pronto_hex([9000, -4500, 560, -560], modulation=38000)
    words = pronto.split()
    assert words[:4] == ["0000", "006D", "0002", "0000"]
    assert len(words) == 8


def test_decode_pronto_hex_roundtrip_shape() -> None:
    """Decode Pronto Hex into alternating signed timings."""
    source = [9000, -4500, 560, -560]
    pronto = encode_raw_to_pronto_hex(source, modulation=38000)
    decoded = decode_pronto_hex_to_raw_timings(pronto)
    assert decoded is not None
    assert len(decoded) == len(source)
    assert [value > 0 for value in decoded[::2]] == [True, True]
    assert [value < 0 for value in decoded[1::2]] == [True, True]


def test_parse_profile_receive_arm_command_fields() -> None:
    """Parse generic receive arm-command configuration from profile."""
    profile = _parse_profile(
        {
            "id": "test_profile",
            "name": "Test profile",
            "match": {},
            "features": {"send_ir": False, "receive_ir": True},
            "transport": {
                "cluster_id": "0xE004",
                "command_id": "0x02",
                "command_arg": "code",
                "expect_reply": False,
            },
            "codec": {"name": "tuya_base64_rawtimings_v1"},
            "receive": {
                "method": "cluster_attribute_read",
                "attribute": "last_learned_ir_code",
                "poll_interval_seconds": 2,
                "arm_command": {
                    "repeat": 30,
                    "min_cmd_interval": 2,
                    "call_cmd": {
                        "command_id": "0x01",
                        "arg": "on_off",
                        "value": True,
                    },
                    "state_cmd": {
                        "cluster_id": "0x0006",
                        "attribute": "on_off",
                        "armed": False,
                        "disarmed": True,
                    },
                    "reset": {
                        "on_receive": True,
                        "on_not_armed": True,
                    },
                },
            },
        }
    )
    assert profile.receive is not None
    assert profile.receive.poll_interval_seconds == 2
    assert profile.receive.arm_command is not None
    assert profile.receive.arm_command.call_command_id == 1
    assert profile.receive.arm_command.call_arg == "on_off"
    assert profile.receive.arm_command.call_value is True
    assert profile.receive.arm_command.state_cluster_id == 0x0006
    assert profile.receive.arm_command.state_attribute == "on_off"
    assert profile.receive.arm_command.state_armed_value is False
    assert profile.receive.arm_command.state_disarmed_value is True
    assert profile.receive.arm_command.min_command_interval_seconds == 2
    assert profile.receive.arm_command.repeat_interval_seconds == 30
    assert profile.receive.arm_command.reset_interval_on_update is True
    assert profile.receive.arm_command.reset_on_arm_value is True
