"""Tests for AsusWRT helpers."""

from typing import Any

import pytest

from homeassistant.components.asuswrt.helpers import clean_dict, translate_to_legacy

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


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        # Case set 0: None as input -> None on output
        (None, None),
        # Case set 1: Dict structure should stay intact or translated
        ({"key1": "value1", "key2": None}, {"key1": "value1", "key2": None}),
        (TRANSLATE_0_INPUT, TRANSLATE_0_OUTPUT),
        (TRANSLATE_1_INPUT, TRANSLATE_1_OUTPUT),
        ({}, {}),
        # Case set 2: List structure should stay intact or translated
        (["key1", "key2"], ["key1", "key2"]),
        (TRANSLATE_2_INPUT, TRANSLATE_2_OUTPUT),
        (TRANSLATE_3_INPUT, TRANSLATE_3_OUTPUT),
        ([], []),
        # Case set 3: Anything else should be simply returned
        (123, 123),
        ("string", "string"),
        (3.1415926535, 3.1415926535),
    ],
)
def test_translate(input: Any, expected: Any) -> None:
    """Test translate method."""

    assert translate_to_legacy(input) == expected
