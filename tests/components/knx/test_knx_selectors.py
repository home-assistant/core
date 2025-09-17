"""Test KNX selectors."""

from typing import Any

import pytest
import voluptuous as vol
from voluptuous_serialize import convert

from homeassistant.components.knx.const import ColorTempModes
from homeassistant.components.knx.storage.knx_selector import (
    AllSerializeFirst,
    GASelector,
    GroupSelect,
    GroupSelectOption,
    KNXSection,
    KNXSectionFlat,
    SyncStateSelector,
)
from homeassistant.components.knx.storage.serialize import knx_serializer
from homeassistant.helpers import selector

INVALID = "invalid"


@pytest.mark.parametrize(
    ("selector_config", "data", "expected"),
    [
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
            {"write": "1/2/3"},
            {"write": "1/2/3", "state": None, "passive": []},
        ),
        (
            {"state_required": True},
            {"state": "1/2/3"},
            {"write": None, "state": "1/2/3", "passive": []},
        ),
        # dpt key
        (
            {"dpt": ColorTempModes},
            {"write": "1/2/3", "dpt": "7.600"},
            {"write": "1/2/3", "state": None, "passive": [], "dpt": "7.600"},
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
    result = selector(data)
    assert result == expected


@pytest.mark.parametrize(
    ("selector_config", "data", "error_str"),
    [
        # empty data is invalid
        (
            {},
            {},
            "At least one group address must be set",
        ),
        (
            {"write": False},
            {},
            "At least one group address must be set",
        ),
        (
            {"passive": False},
            {},
            "At least one group address must be set",
        ),
        (
            {"write": False, "state": False, "passive": False},
            {},
            "At least one group address must be set",
        ),
        # stale data is invalid
        (
            {"write": False},
            {"write": "1/2/3"},
            "At least one group address must be set",
        ),
        (
            {"write": False},
            {"passive": []},
            "At least one group address must be set",
        ),
        (
            {"state": False},
            {"write": None},
            "At least one group address must be set",
        ),
        (
            {"passive": False},
            {"passive": ["1/2/3"]},
            "At least one group address must be set",
        ),
        # required keys
        (
            {"write_required": True},
            {},
            r"required key not provided*",
        ),
        (
            {"state_required": True},
            {},
            r"required key not provided*",
        ),
        (
            {"write_required": True},
            {"state": "1/2/3"},
            r"required key not provided*",
        ),
        (
            {"state_required": True},
            {"write": "1/2/3"},
            r"required key not provided*",
        ),
        # dpt key
        (
            {"dpt": ColorTempModes},
            {"write": "1/2/3"},
            r"required key not provided*",
        ),
        (
            {"dpt": ColorTempModes},
            {"write": "1/2/3", "state": None, "passive": [], "dpt": "invalid"},
            r"value must be one of ['5.001', '7.600', '9']*",
        ),
    ],
)
def test_ga_selector_invalid(
    selector_config: dict[str, Any],
    data: dict[str, Any],
    error_str: str,
) -> None:
    """Test GASelector."""
    selector = GASelector(**selector_config)
    with pytest.raises(vol.Invalid, match=error_str):
        selector(data)


def test_sync_state_selector() -> None:
    """Test SyncStateSelector."""
    selector = SyncStateSelector()
    assert selector("expire 50") == "expire 50"

    with pytest.raises(vol.Invalid):
        selector("invalid")

    with pytest.raises(vol.Invalid, match="Sync state cannot be False"):
        selector(False)

    false_allowed = SyncStateSelector(allow_false=True)
    assert false_allowed(False) is False


@pytest.mark.parametrize(
    ("selector", "serialized"),
    [
        (
            GASelector(),
            {
                "type": "knx_group_address",
                "options": {
                    "write": {"required": False},
                    "state": {"required": False},
                    "passive": True,
                },
            },
        ),
        (
            GASelector(
                state=False, write_required=True, passive=False, valid_dpt="5.001"
            ),
            {
                "type": "knx_group_address",
                "options": {
                    "write": {"required": True},
                    "state": False,
                    "passive": False,
                    "validDPTs": [{"main": 5, "sub": 1}],
                },
            },
        ),
        (
            GASelector(dpt=ColorTempModes),
            {
                "type": "knx_group_address",
                "options": {
                    "write": {"required": False},
                    "state": {"required": False},
                    "passive": True,
                    "dptSelect": [
                        {
                            "value": "7.600",
                            "translation_key": "7_600",
                            "dpt": {"main": 7, "sub": 600},
                        },
                        {
                            "value": "9",
                            "translation_key": "9",
                            "dpt": {"main": 9, "sub": None},
                        },
                        {
                            "value": "5.001",
                            "translation_key": "5_001",
                            "dpt": {"main": 5, "sub": 1},
                        },
                    ],
                },
            },
        ),
    ],
)
def test_ga_selector_serialization(
    selector: GASelector, serialized: dict[str, Any]
) -> None:
    """Test GASelector serialization."""
    assert selector.serialize() == serialized


@pytest.mark.parametrize(
    ("schema", "serialized"),
    [
        (
            AllSerializeFirst(vol.Schema({"key": int}), vol.Schema({"ignored": str})),
            [{"name": "key", "required": False, "type": "integer"}],
        ),
        (
            KNXSectionFlat(collapsible=True),
            {"type": "knx_section_flat", "collapsible": True},
        ),
        (
            KNXSection(
                collapsible=True,
                schema={"key": int},
            ),
            {
                "type": "knx_section",
                "collapsible": True,
                "schema": [{"name": "key", "required": False, "type": "integer"}],
            },
        ),
        (
            GroupSelect(
                GroupSelectOption(translation_key="option_1", schema={"key_1": str}),
                GroupSelectOption(translation_key="option_2", schema={"key_2": int}),
            ),
            {
                "type": "knx_group_select",
                "collapsible": True,
                "schema": [
                    {
                        "type": "knx_group_select_option",
                        "translation_key": "option_1",
                        "schema": [
                            {"name": "key_1", "required": False, "type": "string"}
                        ],
                    },
                    {
                        "type": "knx_group_select_option",
                        "translation_key": "option_2",
                        "schema": [
                            {"name": "key_2", "required": False, "type": "integer"}
                        ],
                    },
                ],
            },
        ),
        (
            SyncStateSelector(),
            {
                "type": "knx_sync_state",
                "allow_false": False,
            },
        ),
        (
            selector.BooleanSelector(),
            {
                "type": "ha_selector",
                "selector": {"boolean": {}},
            },
        ),
        (  # in a dict schema `name` and `required` keys are added
            vol.Schema(
                {
                    "section_test": KNXSectionFlat(),
                    vol.Optional("key"): selector.BooleanSelector(),
                }
            ),
            [
                {
                    "name": "section_test",
                    "type": "knx_section_flat",
                    "required": False,
                    "collapsible": False,
                },
                {
                    "name": "key",
                    "optional": True,
                    "required": False,
                    "type": "ha_selector",
                    "selector": {"boolean": {}},
                },
            ],
        ),
    ],
)
def test_serialization(schema: Any, serialized: dict[str, Any]) -> None:
    """Test serialization of the selector."""
    assert convert(schema, custom_serializer=knx_serializer) == serialized
