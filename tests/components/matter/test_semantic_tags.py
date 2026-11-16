"""Test the Matter child device names from semantic tags and vendor labels."""

from typing import Any
from unittest.mock import MagicMock, patch

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.client.models.device_types import OnOffLight, OnOffPlugInUnit
import pytest

from homeassistant.components.matter.helpers import get_child_device_names
from homeassistant.components.matter.semantic_tags import (
    ChildDeviceName,
    resolve_group_names,
)

from .common import create_node_from_fixture

# The Tapo Smart Wi-Fi Outlet has two On/Off Plug-in Unit endpoints (1 and 2)
# without semantic tags, from a vendor that isn't in the vendor labeling list.
NODE_FIXTURE = "tapo_smart_wi_fi_outlet"

NAMESPACE_COMMON_NUMBER = 0x07
NAMESPACE_COMMON_POSITION = 0x08
LEFT, RIGHT, TOP, BOTTOM, MIDDLE, ROW, COLUMN = range(7)

TP_LINK_DUAL_OUTDOOR_PLUG = {"0/40/2": 4488, "0/40/4": 259}


def _tag(
    namespace: int, tag: int, label: str | None = None, mfg_code: int | None = None
) -> dict[str, Any]:
    """Return a raw semantic tag struct."""
    return {"0": mfg_code, "1": namespace, "2": tag, "3": label}


def _position(*tags: int) -> list[dict[str, Any]]:
    """Return a raw tag list of Common Position tags."""
    return [_tag(NAMESPACE_COMMON_POSITION, tag) for tag in tags]


def _number(*numbers: int) -> list[dict[str, Any]]:
    """Return a raw tag list of Common Number tags."""
    return [_tag(NAMESPACE_COMMON_NUMBER, number) for number in numbers]


def _fixed_label(label: str, value: str) -> list[dict[str, Any]]:
    """Return a raw FixedLabel list with a single label."""
    return [{"0": label, "1": value}]


def _key(translation_key: str, **translation_placeholders: str) -> ChildDeviceName:
    """Return a translated child device name."""
    return ChildDeviceName(
        translation_key=translation_key,
        translation_placeholders=tuple(sorted(translation_placeholders.items()))
        or None,
    )


def _channel(number: str) -> ChildDeviceName:
    """Return a channel child device name."""
    return _key("channel", number=number)


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        pytest.param([TOP], "position_top", id="top"),
        pytest.param([BOTTOM], "position_bottom", id="bottom"),
        pytest.param([LEFT], "position_left", id="left"),
        pytest.param([RIGHT], "position_right", id="right"),
        pytest.param([MIDDLE], "position_middle", id="middle"),
        pytest.param([TOP, LEFT], "position_top_left", id="top_left"),
        pytest.param([TOP, MIDDLE], "position_top_middle", id="top_middle"),
        pytest.param([TOP, RIGHT], "position_top_right", id="top_right"),
        pytest.param([MIDDLE, LEFT], "position_middle_left", id="middle_left"),
        pytest.param([MIDDLE, RIGHT], "position_middle_right", id="middle_right"),
        pytest.param([BOTTOM, LEFT], "position_bottom_left", id="bottom_left"),
        pytest.param([BOTTOM, MIDDLE], "position_bottom_middle", id="bottom_middle"),
        pytest.param([BOTTOM, RIGHT], "position_bottom_right", id="bottom_right"),
    ],
)
def test_position_names(tags: list[int], expected: str) -> None:
    """Test Common Position spatial tags map to one translation key."""
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            "1/29/4": _position(*tags),
            "2/29/4": _position(TOP if TOP not in tags else BOTTOM),
        },
    )
    names = get_child_device_names(node)
    assert names[1] == _key(expected)


@pytest.mark.parametrize(
    "tags",
    [
        pytest.param([TOP, BOTTOM], id="top_bottom"),
        pytest.param([LEFT, RIGHT], id="left_right"),
        pytest.param([TOP, LEFT, MIDDLE], id="top_left_middle"),
    ],
)
def test_invalid_position_combination(tags: list[int]) -> None:
    """Test a set of position tags that isn't a grid cell gives no name."""
    node = create_node_from_fixture(
        NODE_FIXTURE, {"1/29/4": _position(*tags), "2/29/4": _position(TOP)}
    )
    assert get_child_device_names(node) == {}


@pytest.mark.parametrize(
    ("tags_1", "tags_2", "expected"),
    [
        pytest.param(
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "1")],
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "2")],
            {1: _key("row", row="1"), 2: _key("row", row="2")},
            id="row",
        ),
        pytest.param(
            [_tag(NAMESPACE_COMMON_POSITION, COLUMN, "1")],
            [_tag(NAMESPACE_COMMON_POSITION, COLUMN, "12")],
            {1: _key("column", column="1"), 2: _key("column", column="12")},
            id="column",
        ),
        pytest.param(
            [
                _tag(NAMESPACE_COMMON_POSITION, ROW, "1"),
                _tag(NAMESPACE_COMMON_POSITION, COLUMN, "2"),
            ],
            [
                _tag(NAMESPACE_COMMON_POSITION, ROW, "2"),
                _tag(NAMESPACE_COMMON_POSITION, COLUMN, "1"),
            ],
            {
                1: _key("row_column", row="1", column="2"),
                2: _key("row_column", row="2", column="1"),
            },
            id="row_column",
        ),
        pytest.param(
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "0")],
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "1")],
            {},
            id="row_zero",
        ),
        pytest.param(
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "01")],
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "2")],
            {},
            id="row_leading_zero",
        ),
        pytest.param(
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "first")],
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "2")],
            {},
            id="row_not_a_number",
        ),
        pytest.param(
            [_tag(NAMESPACE_COMMON_POSITION, ROW)],
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "2")],
            {},
            id="row_without_label",
        ),
        pytest.param(
            [
                _tag(NAMESPACE_COMMON_POSITION, ROW, "1"),
                _tag(NAMESPACE_COMMON_POSITION, ROW, "3"),
            ],
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "2")],
            {},
            id="several_rows",
        ),
        pytest.param(
            [_tag(NAMESPACE_COMMON_POSITION, ROW, "1\x00\x00")],
            [_tag(NAMESPACE_COMMON_POSITION, ROW, " 2 ")],
            {1: _key("row", row="1"), 2: _key("row", row="2")},
            id="row_padded_label",
        ),
    ],
)
def test_row_column_names(
    tags_1: list[dict[str, Any]],
    tags_2: list[dict[str, Any]],
    expected: dict[int, ChildDeviceName],
) -> None:
    """Test Common Position Row and Column tags."""
    node = create_node_from_fixture(NODE_FIXTURE, {"1/29/4": tags_1, "2/29/4": tags_2})
    assert get_child_device_names(node) == expected


@pytest.mark.parametrize(
    ("tags_1", "tags_2", "expected"),
    [
        pytest.param(
            _number(1),
            _number(2),
            {1: _channel("1"), 2: _channel("2")},
            id="one_number_each",
        ),
        pytest.param(
            _number(0),
            _number(30),
            {1: _channel("0"), 2: _channel("30")},
            id="zero_and_thirty",
        ),
        pytest.param(_number(1, 3), _number(2), {}, id="several_numbers"),
        pytest.param(_number(31), _number(2), {}, id="above_thirty"),
        pytest.param(_number(1), _number(1), {}, id="duplicate_numbers"),
        pytest.param(_number(1), [], {}, id="one_endpoint_unnamed"),
    ],
)
def test_number_names(
    tags_1: list[dict[str, Any]],
    tags_2: list[dict[str, Any]],
    expected: dict[int, ChildDeviceName],
) -> None:
    """Test Common Number tags."""
    node = create_node_from_fixture(NODE_FIXTURE, {"1/29/4": tags_1, "2/29/4": tags_2})
    assert get_child_device_names(node) == expected


def test_source_precedence() -> None:
    """Test the first source naming every endpoint is used for the whole group.

    Endpoint 2 has no position tag, so the position source doesn't name the
    whole group, and the Common Number tags name both endpoints instead.
    """
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            "1/29/4": [*_position(LEFT), *_number(1)],
            "2/29/4": _number(2),
        },
    )
    assert get_child_device_names(node) == {1: _channel("1"), 2: _channel("2")}

    # With position tags on both endpoints, position wins over the number.
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            "1/29/4": [*_position(LEFT), *_number(1)],
            "2/29/4": [*_position(RIGHT), *_number(2)],
        },
    )
    assert get_child_device_names(node) == {
        1: _key("position_left"),
        2: _key("position_right"),
    }


def test_semantic_tags_before_vendor_labels() -> None:
    """Test semantic tags win over vendor labels when both name the group."""
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            **TP_LINK_DUAL_OUTDOOR_PLUG,
            "1/29/4": _position(TOP),
            "2/29/4": _position(BOTTOM),
            "1/64/0": _fixed_label("Position", "1"),
            "2/64/0": _fixed_label("Position", "2"),
        },
    )
    assert get_child_device_names(node) == {
        1: _key("position_top"),
        2: _key("position_bottom"),
    }


def test_position_and_row_not_combined() -> None:
    """Test positions and rows are not combined to name a grid."""
    node = create_node_from_fixture(
        "tapo_smart_wi_fi_power_strip",
        {
            f"{endpoint_id}/29/4": [
                *_position(position),
                _tag(NAMESPACE_COMMON_POSITION, ROW, row),
            ]
            for endpoint_id, position, row in (
                (1, LEFT, "1"),
                (2, RIGHT, "1"),
                (3, LEFT, "2"),
                (4, RIGHT, "2"),
                (5, LEFT, "3"),
                (6, RIGHT, "3"),
            )
        },
    )
    assert get_child_device_names(node) == {}


def test_manufacturer_namespace_tags() -> None:
    """Test tags from a manufacturer namespace.

    Their namespace id isn't matched against the standard namespaces, but their
    label is used as a literal name.
    """
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            "1/29/4": [_tag(NAMESPACE_COMMON_POSITION, TOP, " Kitchen ", 0xFFF1)],
            "2/29/4": [_tag(NAMESPACE_COMMON_POSITION, BOTTOM, "Hall", 0xFFF1)],
        },
    )
    assert get_child_device_names(node) == {
        1: ChildDeviceName(name="Kitchen"),
        2: ChildDeviceName(name="Hall"),
    }

    # Without a label, a manufacturer namespace tag gives no name.
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            "1/29/4": [_tag(NAMESPACE_COMMON_POSITION, TOP, None, 0xFFF1)],
            "2/29/4": [_tag(NAMESPACE_COMMON_POSITION, BOTTOM, None, 0xFFF1)],
        },
    )
    assert get_child_device_names(node) == {}


def test_standard_label_not_used_as_name() -> None:
    """Test the label of a standard namespace tag isn't used as a name."""
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            "1/29/4": [_tag(NAMESPACE_COMMON_NUMBER, 1, "Kitchen"), *_number(2)],
            "2/29/4": [_tag(NAMESPACE_COMMON_NUMBER, 3, "Hall"), *_number(4)],
        },
    )
    assert get_child_device_names(node) == {}


@pytest.mark.parametrize(
    ("value_1", "value_2", "expected"),
    [
        pytest.param("1", "2", {1: _channel("1"), 2: _channel("2")}, id="numbers"),
        pytest.param(
            "Top",
            " bottom ",
            {1: _key("position_top"), 2: _key("position_bottom")},
            id="position_words",
        ),
        pytest.param(
            "1",
            "top",
            {1: ChildDeviceName(name="1"), 2: ChildDeviceName(name="top")},
            id="mixed_number_and_word",
        ),
        pytest.param(
            "Garden",
            "Patio",
            {1: ChildDeviceName(name="Garden"), 2: ChildDeviceName(name="Patio")},
            id="literal",
        ),
        pytest.param(
            "1\x00\x00",
            "2\x00",
            {1: _channel("1"), 2: _channel("2")},
            id="null_padded_numbers",
        ),
        pytest.param("Garden", " ", {}, id="blank_label"),
        pytest.param("Garden", "garden", {}, id="duplicate_literal"),
    ],
)
def test_vendor_label_names(
    value_1: str, value_2: str, expected: dict[int, ChildDeviceName]
) -> None:
    """Test vendor FixedLabels are normalized for the whole group."""
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            **TP_LINK_DUAL_OUTDOOR_PLUG,
            "1/64/0": _fixed_label("Position", value_1),
            "2/64/0": _fixed_label("Position", value_2),
        },
    )
    assert get_child_device_names(node) == expected


def test_vendor_label_requires_listed_product() -> None:
    """Test FixedLabels are only used for products in the vendor labeling list."""
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            "1/64/0": _fixed_label("Position", "1"),
            "2/64/0": _fixed_label("Position", "2"),
        },
    )
    assert get_child_device_names(node) == {}


def test_vendor_label_falls_through_blank_label() -> None:
    """Test a blank value for one listed label name falls through to the next."""
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            # Inovelli VTM30 is listed with "label", "name" and "button".
            "0/40/2": 4961,
            "0/40/4": 16,
            "1/64/0": [{"0": "label", "1": " "}, {"0": "name", "1": "Fan"}],
            "2/64/0": [{"0": "label", "1": ""}, {"0": "name", "1": "Light"}],
        },
    )
    assert get_child_device_names(node) == {
        1: ChildDeviceName(name="Fan"),
        2: ChildDeviceName(name="Light"),
    }


def test_vendor_label_disabled_for_product() -> None:
    """Test no labels are used for a product listed without label names."""
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            # Inovelli VTM36 is listed with None.
            "0/40/2": 4961,
            "0/40/4": 4,
            "1/64/0": _fixed_label("label", "1"),
            "2/64/0": _fixed_label("label", "2"),
        },
    )
    assert get_child_device_names(node) == {}


def test_user_label_not_used() -> None:
    """Test UserLabels, which are writable over Matter, don't name child devices."""
    node = create_node_from_fixture(
        NODE_FIXTURE,
        {
            **TP_LINK_DUAL_OUTDOOR_PLUG,
            "1/65/0": _fixed_label("Position", "1"),
            "2/65/0": _fixed_label("Position", "2"),
        },
    )
    assert get_child_device_names(node) == {}


@pytest.mark.parametrize(
    ("tags_lights", "expected"),
    [
        pytest.param(
            [_number(1), _number(2), _number(3)],
            {},
            id="colliding_groups",
        ),
        pytest.param(
            [_number(4), _number(5), _number(6)],
            {e: _channel(str(e)) for e in range(1, 7)},
            id="distinct_groups",
        ),
        pytest.param(
            [_position(TOP), _position(MIDDLE), _position(BOTTOM)],
            {
                1: _channel("1"),
                2: _channel("2"),
                3: _channel("3"),
                4: _key("position_top"),
                5: _key("position_middle"),
                6: _key("position_bottom"),
            },
            id="different_sources",
        ),
    ],
)
def test_names_distinct_across_groups(
    tags_lights: list[list[dict[str, Any]]], expected: dict[int, ChildDeviceName]
) -> None:
    """Test groups whose names collide with another group's don't split."""
    node = create_node_from_fixture(
        "tapo_smart_wi_fi_power_strip",
        {
            "1/29/4": _number(1),
            "2/29/4": _number(2),
            "3/29/4": _number(3),
            **{
                f"{endpoint_id}/29/0": [{"0": OnOffLight.device_type, "1": 1}]
                for endpoint_id in (4, 5, 6)
            },
            **{
                f"{endpoint_id}/29/4": tags
                for endpoint_id, tags in zip((4, 5, 6), tags_lights, strict=True)
            },
        },
    )
    with patch(
        "homeassistant.components.matter.helpers.CHILD_DEVICE_TYPES",
        {OnOffPlugInUnit, OnOffLight},
    ):
        assert get_child_device_names(node) == expected


def test_literal_name_collides_with_translated_name() -> None:
    """Test a literal name compares equal to the translated name it reads as."""
    assert ChildDeviceName(name="TOP").comparison_key == _key("position_top")
    assert ChildDeviceName(name="2").comparison_key == _channel("2")
    assert ChildDeviceName(name="Garden").comparison_key == ChildDeviceName(
        name="garden"
    )


@pytest.mark.parametrize("mfg_code", [None, NullValue])
def test_null_manufacturer_code_is_standard(mfg_code: Any) -> None:
    """Test both None and NullValue manufacturer codes mark a standard tag."""
    endpoints = []
    for endpoint_id, position in ((1, TOP), (2, BOTTOM)):
        endpoint = MagicMock(endpoint_id=endpoint_id)
        endpoint.get_attribute_value.side_effect = lambda _, attribute, pos=position: (
            [
                clusters.Globals.Structs.semtag(
                    mfgCode=mfg_code,
                    namespaceID=NAMESPACE_COMMON_POSITION,
                    tag=pos,
                    label=None,
                )
            ]
            if attribute is clusters.Descriptor.Attributes.TagList
            else None
        )
        endpoints.append(endpoint)

    assert resolve_group_names(endpoints) == {
        1: _key("position_top"),
        2: _key("position_bottom"),
    }
