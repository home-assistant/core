"""Tests for AsusWRT helpers."""

from homeassistant.components.asuswrt.helpers import clean_dict

DICT_TO_CLEAN = {
    "key1": "value1",
    "key2": None,
    "key3_state": "value3",
    "key4_state": None,
    "state": None,
}

DICT_CLEAN = {
    "key1": "value1",
    "key3_state": "value3",
    "key4_state": None,
    "state": None,
}

TRANSLATE_0_INPUT = {
    "usage": "value1",
    "cpu": "value2",
}

TRANSLATE_0_OUTPUT = {
    "mem_usage_perc": "value1",
    "CPU": "value2",
}

TRANSLATE_1_INPUT = {
    "wan_rx": "value1",
    "wan_rrx": "value2",
}

TRANSLATE_1_OUTPUT = {
    "sensor_rx_bytes": "value1",
    "wan_rrx": "value2",
}

TRANSLATE_2_INPUT = [
    "free",
    "used",
]

TRANSLATE_2_OUTPUT = [
    "mem_free",
    "mem_used",
]

TRANSLATE_3_INPUT = [
    "2ghz",
    "2ghz2",
]

TRANSLATE_3_OUTPUT = [
    "2.4GHz",
    "2ghz2",
]


def test_clean_dict() -> None:
    """Test clean_dict method."""

    assert clean_dict(DICT_TO_CLEAN) == DICT_CLEAN
