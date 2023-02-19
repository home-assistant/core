"""Test the helper functions."""

from homeassistant.components.envisalink.helpers import (
    find_yaml_info,
    generate_range_string,
    parse_range_string,
)


async def test_range_parsing() -> None:
    """Test zone/partition set parsing functions."""
    min_val = 1
    max_val = 128

    test_strings = [
        ("1-8,16-29", True, "1-8,16-29"),
        ("1-8", True, "1-8"),
        ("1-20,25-26,42", True, "1-20,25-26,42"),
        ("3-9,20-23,1,12-14", True, "1,3-9,12-14,20-23"),
        (f"1,2,{max_val}", True, f"1-2,{max_val}"),
        (f"1,{min_val},5", True, "1,5"),
        ("1-2,g,b", False),
        ("1,2,3-", False),
        ("1,-3,4", False),
        (f"1,2,{max_val+1}", False),
        (f"1,{min_val-1},5", False),
        ("1-2-3", False),
        ("8-2", False),
        ("", False),
        ("-", False),
        (",", False),
        (",-", False),
    ]

    for idx, item in enumerate(test_strings):
        result = parse_range_string(item[0], min_val, max_val)
        success = result is not None
        assert success is item[1], f"parse_range_string failed at index {idx}"
        if item[1]:
            seq = generate_range_string(result)
            assert seq == item[2], f"generate_range_string failed at index {idx}"

    result = generate_range_string(set())
    assert not result


async def test_find_yaml_info() -> None:
    """Test extracting zone/partition info from configuration.yaml-based config."""
    info = {"01": "Zone 1", 2: "Zone 2"}

    assert find_yaml_info(1, info)
    assert find_yaml_info(2, info)
    assert not find_yaml_info(3, info)
    assert not find_yaml_info(3, None)
