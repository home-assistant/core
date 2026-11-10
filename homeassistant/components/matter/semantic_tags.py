"""Name Matter child devices from semantic tags and vendor labels.

Each name source is used on its own, never combined with another one. So for
example a grid tagged with Left/Right plus a Row number on every endpoint isn't
named, as neither the positions nor the rows alone are distinct.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue

from .const import VENDOR_LABELING_LIST
from .util import get_clean_name

if TYPE_CHECKING:
    from matter_server.client.models.node import MatterEndpoint

NAMESPACE_COMMON_NUMBER = clusters.Globals.Enums.namespace.kCommonNumber
NAMESPACE_COMMON_POSITION = clusters.Globals.Enums.namespace.kCommonPosition

# Common Position namespace tags
POSITION_LEFT = 0x00
POSITION_RIGHT = 0x01
POSITION_TOP = 0x02
POSITION_BOTTOM = 0x03
POSITION_MIDDLE = 0x04
POSITION_ROW = 0x05
POSITION_COLUMN = 0x06

# Common Number namespace tags are the number itself, from Zero to Thirty.
MAX_COMMON_NUMBER = 0x1E

# Row and Column labels, and numeric vendor labels, are numbers starting at 1.
NUMBER_LABEL = re.compile(r"[1-9][0-9]*")
# Vendor labels that are position words get the matching position name.
POSITION_WORDS = {"left", "right", "top", "bottom", "middle"}


# One translation key per set of Common Position spatial tags, so each language
# can choose its own word order. Combined with Top or Bottom, Middle names the
# column; combined with Left or Right, it names the row; on its own it is the
# center. Any other set of tags gives no name.
POSITION_KEYS: dict[frozenset[int], str] = {
    frozenset({POSITION_TOP}): "position_top",
    frozenset({POSITION_BOTTOM}): "position_bottom",
    frozenset({POSITION_LEFT}): "position_left",
    frozenset({POSITION_RIGHT}): "position_right",
    frozenset({POSITION_MIDDLE}): "position_middle",
    frozenset({POSITION_TOP, POSITION_LEFT}): "position_top_left",
    frozenset({POSITION_TOP, POSITION_MIDDLE}): "position_top_middle",
    frozenset({POSITION_TOP, POSITION_RIGHT}): "position_top_right",
    frozenset({POSITION_MIDDLE, POSITION_LEFT}): "position_middle_left",
    frozenset({POSITION_MIDDLE, POSITION_RIGHT}): "position_middle_right",
    frozenset({POSITION_BOTTOM, POSITION_LEFT}): "position_bottom_left",
    frozenset({POSITION_BOTTOM, POSITION_MIDDLE}): "position_bottom_middle",
    frozenset({POSITION_BOTTOM, POSITION_RIGHT}): "position_bottom_right",
}


@dataclass(frozen=True, kw_only=True)
class ChildDeviceName:
    """Name of a child device, either a translation key or a literal name."""

    translation_key: str | None = None
    # A tuple instead of a dict to keep the dataclass hashable.
    translation_placeholders: tuple[tuple[str, str], ...] | None = None
    name: str | None = None

    @property
    def comparison_key(self) -> ChildDeviceName:
        """Return a language independent form of the name to compare names.

        A literal name that reads like a translated name (a number or a
        position word) compares equal to that translated name.
        """
        if self.name is None:
            return self
        return _keyed_label_name(self.name) or ChildDeviceName(
            name=self.name.casefold()
        )


def _channel_name(number: str) -> ChildDeviceName:
    """Return the name of a numbered channel."""
    return ChildDeviceName(
        translation_key="channel", translation_placeholders=(("number", number),)
    )


def _keyed_label_name(value: str) -> ChildDeviceName | None:
    """Return the translated name for a numeric or position word label."""
    if NUMBER_LABEL.fullmatch(value):
        return _channel_name(value)
    if value.casefold() in POSITION_WORDS:
        return ChildDeviceName(translation_key=f"position_{value.casefold()}")
    return None


def _semantic_tags(endpoint: MatterEndpoint) -> list[clusters.Globals.Structs.semtag]:
    """Return the semantic tags of the endpoint."""
    return (
        endpoint.get_attribute_value(None, clusters.Descriptor.Attributes.TagList) or []
    )


def _standard_tags(endpoint: MatterEndpoint) -> list[clusters.Globals.Structs.semtag]:
    """Return the semantic tags of the endpoint from standard namespaces.

    A tag with a manufacturer code belongs to a namespace of that manufacturer,
    so its namespace id can't be matched against the standard namespaces.
    """
    return [tag for tag in _semantic_tags(endpoint) if tag.mfgCode in (None, NullValue)]


def _position_name(endpoint: MatterEndpoint) -> ChildDeviceName | None:
    """Return the name from Common Position spatial tags."""
    tags = frozenset(
        tag.tag
        for tag in _standard_tags(endpoint)
        if tag.namespaceID == NAMESPACE_COMMON_POSITION and tag.tag <= POSITION_MIDDLE
    )
    if (key := POSITION_KEYS.get(tags)) is None:
        return None
    return ChildDeviceName(translation_key=key)


def _row_column_name(endpoint: MatterEndpoint) -> ChildDeviceName | None:
    """Return the name from Common Position Row and Column tags."""
    found: dict[str, str] = {}
    for tag in _standard_tags(endpoint):
        if tag.namespaceID != NAMESPACE_COMMON_POSITION or tag.tag not in (
            POSITION_ROW,
            POSITION_COLUMN,
        ):
            continue
        key = "row" if tag.tag == POSITION_ROW else "column"
        # The label is the row or column number, starting at 1, and an endpoint
        # has at most one row and one column.
        label = get_clean_name(tag.label) if isinstance(tag.label, str) else None
        if key in found or label is None or not NUMBER_LABEL.fullmatch(label):
            return None
        found[key] = label
    if not found:
        return None
    key = "row_column" if len(found) == 2 else next(iter(found))
    return ChildDeviceName(
        translation_key=key, translation_placeholders=tuple(sorted(found.items()))
    )


def _number_name(endpoint: MatterEndpoint) -> ChildDeviceName | None:
    """Return the name from a single Common Number tag."""
    numbers = [
        tag.tag
        for tag in _standard_tags(endpoint)
        if tag.namespaceID == NAMESPACE_COMMON_NUMBER
    ]
    if len(numbers) != 1 or not 0 <= numbers[0] <= MAX_COMMON_NUMBER:
        return None
    return _channel_name(str(numbers[0]))


def _manufacturer_tag_label_name(endpoint: MatterEndpoint) -> ChildDeviceName | None:
    """Return the name from the label of a manufacturer namespace tag."""
    for tag in _semantic_tags(endpoint):
        if (
            tag.mfgCode not in (None, NullValue)
            and isinstance(tag.label, str)
            and (label := get_clean_name(tag.label))
        ):
            return ChildDeviceName(name=label)
    return None


def get_labeling_list(endpoint: MatterEndpoint) -> list[str]:
    """Return the label names to use for the endpoint's vendor and product."""
    if (device_info := endpoint.device_info) is None:
        return []
    return (
        VENDOR_LABELING_LIST.get(device_info.vendorID, {}).get(device_info.productID)
        or []
    )


def _vendor_label(endpoint: MatterEndpoint) -> str | None:
    """Return the first matching vendor FixedLabel value of the endpoint.

    UserLabel is not used, as it is writable over Matter and a label edit would
    rename the child device.
    """
    fixed_labels: list[clusters.FixedLabel.Structs.LabelStruct] = (
        endpoint.get_attribute_value(None, clusters.FixedLabel.Attributes.LabelList)
        or []
    )
    for label_name in get_labeling_list(endpoint):
        for label in fixed_labels:
            if label.label.lower() == label_name and (
                value := get_clean_name(label.value)
            ):
                return value
    return None


def _vendor_label_names(
    endpoints: Sequence[MatterEndpoint],
) -> dict[int, ChildDeviceName] | None:
    """Return the names of a group from vendor labels, normalized group-wide.

    All labels being numbers, or all being position words, gives translated
    names; otherwise every label is used as a literal name. So all endpoints of
    a group get the same kind of name.
    """
    labels: dict[int, str] = {}
    for endpoint in endpoints:
        if (label := _vendor_label(endpoint)) is None:
            return None
        labels[endpoint.endpoint_id] = label
    keyed = {
        endpoint_id: _keyed_label_name(label) for endpoint_id, label in labels.items()
    }
    keyed_names = [name for name in keyed.values() if name is not None]
    if len(keyed_names) == len(keyed) and (
        len({name.translation_key == "channel" for name in keyed_names}) == 1
    ):
        return {
            endpoint_id: name for endpoint_id, name in keyed.items() if name is not None
        }
    return {
        endpoint_id: ChildDeviceName(name=label)
        for endpoint_id, label in labels.items()
    }


def _per_endpoint(
    source: Callable[[MatterEndpoint], ChildDeviceName | None],
) -> Callable[[Sequence[MatterEndpoint]], dict[int, ChildDeviceName] | None]:
    """Return a group source that names every endpoint from a per endpoint source."""

    def group_source(
        endpoints: Sequence[MatterEndpoint],
    ) -> dict[int, ChildDeviceName] | None:
        names: dict[int, ChildDeviceName] = {}
        for endpoint in endpoints:
            if (name := source(endpoint)) is None:
                return None
            names[endpoint.endpoint_id] = name
        return names

    return group_source


# Name sources in order of preference. Semantic tags are the standard source,
# the curated vendor labels come before free text manufacturer tag labels.
NAME_SOURCES: tuple[
    Callable[[Sequence[MatterEndpoint]], dict[int, ChildDeviceName] | None], ...
] = (
    _per_endpoint(_position_name),
    _per_endpoint(_row_column_name),
    _per_endpoint(_number_name),
    _vendor_label_names,
    _per_endpoint(_manufacturer_tag_label_name),
)


def _names_are_distinct(names: Iterable[ChildDeviceName]) -> bool:
    """Return if the names are distinct, independent of language."""
    names = list(names)
    return len({name.comparison_key for name in names}) == len(names)


def resolve_group_names(
    endpoints: Sequence[MatterEndpoint],
) -> dict[int, ChildDeviceName] | None:
    """Return the child device names of a group of sibling endpoints.

    The first source that names every endpoint of the group with distinct names
    is used for the whole group. If no source does, return None.
    """
    for source in NAME_SOURCES:
        if (names := source(endpoints)) is not None and _names_are_distinct(
            names.values()
        ):
            return names
    return None
