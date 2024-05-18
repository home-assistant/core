"""Test KNX selectors."""

import pytest
import voluptuous as vol

from homeassistant.components.knx.const import ColorTempModes
from homeassistant.components.knx.storage.knx_selector import GASelector

INVALID = "invalid"


@pytest.mark.parametrize(
    ("selector_config", "data", "expected"),
    [
        (
            {},
            {},
            {"write": None, "state": None, "passive": []},
        ),
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
            {"write": "1/2/3"},
            {"state": None, "passive": []},
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
            {"passive": ["1/2/3"]},
            {"write": None, "state": None},
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
            INVALID,
        ),
        (
            {"state_required": True},
            {},
            INVALID,
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
            INVALID,
        ),
        (
            {"state_required": True},
            {"write": "1/2/3"},
            INVALID,
        ),
        # dpt key
        (
            {"dpt": ColorTempModes},
            {"write": "1/2/3"},
            INVALID,
        ),
        (
            {"dpt": ColorTempModes},
            {"write": "1/2/3", "dpt": "7.600"},
            {"write": "1/2/3", "state": None, "passive": [], "dpt": "7.600"},
        ),
        (
            {"dpt": ColorTempModes},
            {"write": "1/2/3", "state": None, "passive": [], "dpt": "invalid"},
            INVALID,
        ),
    ],
)
def test_ga_selector(selector_config, data, expected):
    """Test GASelector."""
    selector = GASelector(**selector_config)
    if expected == INVALID:
        with pytest.raises(vol.Invalid):
            selector(data)
    else:
        result = selector(data)
        assert result == expected
