"""Test KNX selectors."""

from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.knx.const import ColorTempModes
from homeassistant.components.knx.storage.knx_selector import GASelector

INVALID = "invalid"


@pytest.mark.parametrize(
    ("selector_config", "data", "expected"),
    [
        # empty data is invalid
        (
            {},
            {},
            {INVALID: "At least one group address must be set"},
        ),
        (
            {"write": False},
            {},
            {INVALID: "At least one group address must be set"},
        ),
        (
            {"passive": False},
            {},
            {INVALID: "At least one group address must be set"},
        ),
        (
            {"write": False, "state": False, "passive": False},
            {},
            {INVALID: "At least one group address must be set"},
        ),
        # stale data is invalid
        (
            {"write": False},
            {"write": "1/2/3"},
            {INVALID: "At least one group address must be set"},
        ),
        (
            {"write": False},
            {"passive": []},
            {INVALID: "At least one group address must be set"},
        ),
        (
            {"state": False},
            {"write": None},
            {INVALID: "At least one group address must be set"},
        ),
        (
            {"passive": False},
            {"passive": ["1/2/3"]},
            {INVALID: "At least one group address must be set"},
        ),
        # valid data
        (
            {},
            {"write": "1/2/3"},
            {"write": "1/2/3", "state": None, "passive": []},
        ),
        (
            {},
            {"state": "1/2/3"},
            {"write": None, "state": "1/2/3", "passive": []},
        ),
        (
            {},
            {"passive": ["1/2/3"]},
            {"write": None, "state": None, "passive": ["1/2/3"]},
        ),
        (
            {},
            {"write": "1", "state": 2, "passive": ["1/2/3"]},
            {"write": "1", "state": 2, "passive": ["1/2/3"]},
        ),
        (
            {"write": False},
            {"state": "1/2/3"},
            {"state": "1/2/3", "passive": []},
        ),
        (
            {"write": False},
            {"passive": ["1/2/3"]},
            {"state": None, "passive": ["1/2/3"]},
        ),
        (
            {"passive": False},
            {"write": "1/2/3"},
            {"write": "1/2/3", "state": None},
        ),
        # required keys
        (
            {"write_required": True},
            {},
            {INVALID: r"required key not provided*"},
        ),
        (
            {"state_required": True},
            {},
            {INVALID: r"required key not provided*"},
        ),
        (
            {"write_required": True},
            {"write": "1/2/3"},
            {"write": "1/2/3", "state": None, "passive": []},
        ),
        (
            {"state_required": True},
            {"state": "1/2/3"},
            {"write": None, "state": "1/2/3", "passive": []},
        ),
        (
            {"write_required": True},
            {"state": "1/2/3"},
            {INVALID: r"required key not provided*"},
        ),
        (
            {"state_required": True},
            {"write": "1/2/3"},
            {INVALID: r"required key not provided*"},
        ),
        # dpt key
        (
            {"dpt": ColorTempModes},
            {"write": "1/2/3"},
            {INVALID: r"required key not provided*"},
        ),
        (
            {"dpt": ColorTempModes},
            {"write": "1/2/3", "dpt": "7.600"},
            {"write": "1/2/3", "state": None, "passive": [], "dpt": "7.600"},
        ),
        (
            {"dpt": ColorTempModes},
            {"write": "1/2/3", "state": None, "passive": [], "dpt": "invalid"},
            {INVALID: r"value must be one of ['5.001', '7.600', '9']*"},
        ),
    ],
)
def test_ga_selector(
    selector_config: dict[str, Any],
    data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test GASelector."""
    selector = GASelector(**selector_config)
    if INVALID in expected:
        with pytest.raises(vol.Invalid, match=expected[INVALID]):
            selector(data)
    else:
        result = selector(data)
        assert result == expected
