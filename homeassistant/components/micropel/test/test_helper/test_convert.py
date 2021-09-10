"""Test conversions."""
from ...helper import convert


def test_int_to_hex():
    """Test conversion between int and hex string."""
    expected = "16"
    result = convert.int_to_hex(0x16, 2)
    assert expected == result

    expected = "0016"
    result = convert.int_to_hex(0x16, 4)
    assert expected == result

    expected = "02"
    result = convert.int_to_hex(0x02, 2)
    assert expected == result

    expected = "0000"
    result = convert.int_to_hex(0, 4)
    assert expected == result
