"""Blocks of triggers, conditions and actions with an item at a known path.

A block is what a user writes for triggers, conditions or actions: a list or
a single item, in any of the forms the schemas accept. The generator puts one
item, the marker, in a block and returns the path of the marker in the block
as it is written. The path is known from how the block was built, not from
any validator.
"""

from collections.abc import Callable, Iterator
import copy
from dataclasses import dataclass, field
import itertools
import random
from typing import Any, Literal

import probatio

from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

type BlockKind = Literal["triggers", "conditions", "actions"]
type Path = tuple[str | int, ...]

OK_TRIGGER = {"trigger": "event", "event_type": "test_event"}
OK_CONDITION = {"condition": "state", "entity_id": "light.kitchen", "state": "on"}
OK_ACTION = {"delay": 1}

REGISTRY_ID = "0123456789abcdef0123456789abcdef"

# The forms which are not the same in a block as written and as validated
SINGLE = "single item"
SUBLIST = "trigger sublist"
SHORTHAND = "condition shorthand"
PARALLEL = "parallel shorthand"

_OK: dict[BlockKind, dict[str, Any]] = {
    "triggers": OK_TRIGGER,
    "conditions": OK_CONDITION,
    "actions": OK_ACTION,
}


@dataclass(frozen=True)
class Marker:
    """An item without nested blocks, and the error it gives if it is invalid.

    path is the path of the error below the item.
    """

    name: str
    item: dict[str, Any]
    path: Path = ()
    exception: type[Exception] | None = None
    message: str | None = None


# Items which pass their schema and are rejected by their platform
PLATFORM_ERROR_MARKERS: dict[BlockKind, tuple[Marker, ...]] = {
    "triggers": (
        Marker(
            "registry",
            {"trigger": "state", "entity_id": REGISTRY_ID},
            (),
            probatio.Invalid,
            f"Unknown entity registry entry {REGISTRY_ID}",
        ),
        Marker(
            "field",
            {"trigger": "numeric_state", "above": 1},
            ("entity_id",),
            probatio.RequiredFieldInvalid,
            "required key not provided",
        ),
        Marker(
            "device",
            {"trigger": "device", "domain": "light", "device_id": "abc"},
            (),
            InvalidDeviceAutomationConfig,
            "Unknown device 'abc'",
        ),
    ),
    "conditions": (
        Marker(
            "registry",
            {"condition": "state", "entity_id": REGISTRY_ID, "state": "on"},
            (),
            probatio.Invalid,
            f"Unknown entity registry entry {REGISTRY_ID}",
        ),
        Marker(
            "field",
            {"condition": "device", "device_id": "", "domain": "light"},
            ("device_id",),
            probatio.RequiredFieldInvalid,
            "required value is empty",
        ),
        Marker(
            "unknown",
            {"condition": "non_existing"},
            (),
            HomeAssistantError,
            'Invalid condition "non_existing" specified',
        ),
    ),
    "actions": (
        Marker(
            "device",
            {"device_id": "abc", "domain": "light", "type": "turn_on"},
            (),
            InvalidDeviceAutomationConfig,
            "Unknown device 'abc'",
        ),
        Marker(
            "field",
            {"device_id": "", "domain": "light"},
            ("device_id",),
            probatio.RequiredFieldInvalid,
            "required value is empty",
        ),
        Marker(
            "condition",
            {"condition": "state", "entity_id": REGISTRY_ID, "state": "on"},
            (),
            probatio.Invalid,
            f"Unknown entity registry entry {REGISTRY_ID}",
        ),
    ),
}

# Items which are rejected by the schema of their block
SCHEMA_ERROR_MARKERS: dict[BlockKind, tuple[Marker, ...]] = {
    "triggers": (Marker("no_platform", {"alias": "No platform"}, ("trigger",)),),
    "conditions": (
        Marker(
            "no_state",
            {"condition": "state", "entity_id": "light.kitchen"},
            ("state",),
        ),
    ),
    "actions": (Marker("extra_key", {"delay": 1, "bogus": 2}, ("bogus",)),),
}

# Valid items, which the schema or the platform changes
VALID_MARKERS: dict[BlockKind, tuple[Marker, ...]] = {
    "triggers": (
        Marker(
            "state",
            {"trigger": "state", "entity_id": "light.kitchen", "for": "00:00:05"},
        ),
    ),
    "conditions": (
        Marker(
            "numeric_state",
            {"condition": "numeric_state", "entity_id": "sensor.a", "above": 1},
        ),
    ),
    "actions": (
        Marker(
            "service",
            {"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}},
        ),
    ),
}


@dataclass(frozen=True)
class Case:
    """A block which holds one marker.

    path is the path of the marker's error in the block: the path of the
    marker followed by the path of the error below it. nested_blocks holds the
    (action type, block key) of the nested blocks the marker is in.
    """

    id: str
    group: str
    kind: BlockKind
    submitted: Any
    path: Path
    marker: Marker
    forms: frozenset[str]
    nested_blocks: frozenset[tuple[str, str]]

    @property
    def marker_path(self) -> Path:
        """Return the path of the marker in the block."""
        return self.path[: len(self.path) - len(self.marker.path)]


# A block or an item, the path of the marker in it, its forms and nested blocks
type _Built = tuple[Any, Path, frozenset[str], frozenset[tuple[str, str]]]

_NO_FORMS: frozenset[str] = frozenset()
_SINGLE = frozenset({SINGLE})
_SUBLIST = frozenset({SUBLIST})
_SINGLE_SUBLIST = frozenset({SUBLIST, SINGLE})
_SHORTHAND = frozenset({SHORTHAND})
_PARALLEL = frozenset({PARALLEL})


def _list_forms(
    kind: BlockKind, item: Any
) -> Iterator[tuple[Any, Path, frozenset[str]]]:
    """Yield the ways to write a block of kind which holds item."""
    ok = _OK[kind]
    yield item, (), _SINGLE
    yield [item], (0,), _NO_FORMS
    yield [ok, item, ok], (1,), _NO_FORMS
    if kind != "triggers":
        return
    # A sublist takes one index in the list it is in, however many triggers
    # it holds
    yield [{"triggers": [ok, ok]}, item], (1,), _SUBLIST
    yield [ok, {"triggers": [ok, item]}, ok], (1, "triggers", 1), _SUBLIST
    yield (
        [{"triggers": [ok, ok]}, {"triggers": [item, ok]}],
        (1, "triggers", 0),
        _SUBLIST,
    )
    yield (
        [{"triggers": [ok, ok, ok]}, ok, {"triggers": [ok]}, {"triggers": [ok, item]}],
        (3, "triggers", 1),
        _SUBLIST,
    )
    yield (
        [{"triggers": []}, {"triggers": None}, {"triggers": [ok]}, item],
        (3,),
        _SUBLIST,
    )
    # A sublist which is a single trigger
    yield [{"triggers": item}], (0, "triggers"), _SINGLE_SUBLIST
    yield [ok, {"triggers": ok}, {"triggers": item}], (2, "triggers"), _SINGLE_SUBLIST
    # The block is a single sublist
    yield {"triggers": [item]}, ("triggers", 0), _SINGLE_SUBLIST
    yield {"triggers": [ok, item]}, ("triggers", 1), _SINGLE_SUBLIST
    yield {"triggers": item}, ("triggers",), _SINGLE_SUBLIST


@dataclass(frozen=True)
class _Wrapper:
    """A way to nest a block in an item of another block.

    path is the path of the block in the item. block_key is the key of the
    block in script._NESTED_BLOCKS, for a block nested in an action.
    """

    build: Callable[[Any], dict[str, Any]]
    path: Path
    forms: frozenset[str] = _NO_FORMS
    block_key: str | None = None
    only_list: bool = False

    @property
    def nested_block(self) -> tuple[str, str] | None:
        """Return the (action type, block key) of the block."""
        if self.block_key is None:
            return None
        return cv.determine_script_action(self.build([])), self.block_key


_OK_OPTION = {"conditions": [OK_CONDITION], "sequence": [OK_ACTION]}

_CONDITION_WRAPPERS = (
    _Wrapper(lambda b: {"condition": "and", "conditions": b}, ("conditions",)),
    _Wrapper(lambda b: {"condition": "or", "conditions": b}, ("conditions",)),
    _Wrapper(lambda b: {"condition": "not", "conditions": b}, ("conditions",)),
    _Wrapper(lambda b: {"and": b}, ("and",), _SHORTHAND),
    _Wrapper(lambda b: {"or": b}, ("or",), _SHORTHAND),
    _Wrapper(lambda b: {"not": b}, ("not",), _SHORTHAND),
    _Wrapper(lambda b: {"condition": b}, ("condition",), _SHORTHAND, only_list=True),
    _Wrapper(lambda b: {"alias": "x", "or": b}, ("or",), _SHORTHAND),
)

# (kind of the item, kind of the block nested in it) -> wrappers
_WRAPPERS: dict[tuple[BlockKind, BlockKind], tuple[_Wrapper, ...]] = {
    ("conditions", "conditions"): _CONDITION_WRAPPERS,
    ("actions", "conditions"): (
        *_CONDITION_WRAPPERS,
        _Wrapper(lambda b: {"if": b, "then": [OK_ACTION]}, ("if",), block_key="if"),
        _Wrapper(
            lambda b: {"repeat": {"while": b, "sequence": [OK_ACTION]}},
            ("repeat", "while"),
            block_key="while",
        ),
        _Wrapper(
            lambda b: {"repeat": {"until": b, "sequence": OK_ACTION}},
            ("repeat", "until"),
            block_key="until",
        ),
        _Wrapper(
            lambda b: {"choose": [{"conditions": b, "sequence": [OK_ACTION]}]},
            ("choose", 0, "conditions"),
            block_key="conditions",
        ),
        _Wrapper(
            lambda b: {"choose": {"conditions": b, "sequence": OK_ACTION}},
            ("choose", "conditions"),
            _SINGLE,
            block_key="conditions",
        ),
        _Wrapper(
            lambda b: {
                "choose": [_OK_OPTION, {"conditions": b, "sequence": [OK_ACTION]}],
                "default": [OK_ACTION],
            },
            ("choose", 1, "conditions"),
            block_key="conditions",
        ),
    ),
    ("actions", "actions"): (
        _Wrapper(
            lambda b: {"if": [OK_CONDITION], "then": b}, ("then",), block_key="then"
        ),
        _Wrapper(
            lambda b: {"if": OK_CONDITION, "then": [OK_ACTION], "else": b},
            ("else",),
            block_key="else",
        ),
        _Wrapper(
            lambda b: {"choose": [_OK_OPTION], "default": b},
            ("default",),
            block_key="default",
        ),
        _Wrapper(
            lambda b: {"choose": [], "default": b}, ("default",), block_key="default"
        ),
        _Wrapper(
            lambda b: {
                "choose": [_OK_OPTION, {"conditions": [OK_CONDITION], "sequence": b}]
            },
            ("choose", 1, "sequence"),
            block_key="sequence",
        ),
        _Wrapper(
            lambda b: {"choose": {"conditions": [OK_CONDITION], "sequence": b}},
            ("choose", "sequence"),
            _SINGLE,
            block_key="sequence",
        ),
        _Wrapper(
            lambda b: {"repeat": {"count": 2, "sequence": b}},
            ("repeat", "sequence"),
            block_key="sequence",
        ),
        _Wrapper(lambda b: {"sequence": b}, ("sequence",), block_key="sequence"),
        _Wrapper(
            lambda b: {"alias": "x", "sequence": b, "metadata": {}},
            ("sequence",),
            block_key="sequence",
        ),
        # A parallel branch which is a sequence action, in a list or single
        _Wrapper(
            lambda b: {"parallel": [OK_ACTION, {"sequence": b}]},
            ("parallel", 1, "sequence"),
            block_key="sequence",
        ),
        _Wrapper(
            lambda b: {"parallel": {"sequence": b}},
            ("parallel", "sequence"),
            _SINGLE,
            block_key="sequence",
        ),
        # A parallel branch which is the block: an action or a list of actions
        _Wrapper(
            lambda b: {"parallel": [[OK_ACTION], b, {"sequence": [OK_ACTION]}]},
            ("parallel", 1),
            _PARALLEL,
            block_key="sequence",
        ),
        # The block is the value of parallel: each of its items is a branch
        _Wrapper(
            lambda b: {"parallel": b}, ("parallel",), _PARALLEL, block_key="sequence"
        ),
    ),
    ("actions", "triggers"): (
        _Wrapper(
            lambda b: {"wait_for_trigger": b},
            ("wait_for_trigger",),
            block_key="wait_for_trigger",
        ),
        _Wrapper(
            lambda b: {"wait_for_trigger": b, "timeout": 5, "alias": "x"},
            ("wait_for_trigger",),
            block_key="wait_for_trigger",
        ),
    ),
}

_KINDS: tuple[BlockKind, ...] = ("triggers", "conditions", "actions")
_NESTED_KINDS: dict[BlockKind, tuple[BlockKind, ...]] = {
    "triggers": (),
    "conditions": ("conditions",),
    "actions": ("conditions", "actions", "triggers"),
}


def _wrap(wrapper: _Wrapper, built: _Built) -> _Built | None:
    """Return the item which nests a block with wrapper."""
    block, path, forms, nested_blocks = built
    if wrapper.only_list and not isinstance(block, list):
        return None
    if (nested_block := wrapper.nested_block) is not None:
        nested_blocks |= {nested_block}
    return (
        wrapper.build(block),
        (*wrapper.path, *path),
        forms | wrapper.forms,
        nested_blocks,
    )


def _items(
    kind: BlockKind, depth: int, marker: Marker, marker_kind: BlockKind
) -> Iterator[_Built]:
    """Yield items of kind with the marker exactly depth blocks below them."""
    if depth == 0:
        if kind == marker_kind:
            yield marker.item, (), _NO_FORMS, frozenset()
        return
    for nested_kind in _NESTED_KINDS[kind]:
        for wrapper in _WRAPPERS[kind, nested_kind]:
            for built in _blocks(nested_kind, depth - 1, marker, marker_kind):
                if (item := _wrap(wrapper, built)) is not None:
                    yield item


def _blocks(
    kind: BlockKind, depth: int, marker: Marker, marker_kind: BlockKind
) -> Iterator[_Built]:
    """Yield blocks of kind with the marker depth blocks below their items."""
    for item, path, forms, nested_blocks in _items(kind, depth, marker, marker_kind):
        for block, prefix, list_forms in _list_forms(kind, item):
            yield block, (*prefix, *path), forms | list_forms, nested_blocks


def corpus(
    markers: dict[BlockKind, tuple[Marker, ...]], max_depth: int = 1
) -> list[Case]:
    """Return every block which holds one of the markers.

    The marker is an item of the block, or of a block nested in one of its
    items, up to max_depth nested blocks deep.
    """
    cases: list[Case] = []
    for kind, depth, marker_kind in itertools.product(
        _KINDS, range(max_depth + 1), _KINDS
    ):
        for marker in markers[marker_kind]:
            group = f"{kind}-depth_{depth}-{marker_kind}_{marker.name}"
            cases.extend(
                Case(
                    f"{group}-{index}",
                    group,
                    kind,
                    # A copy, the blocks must not share items
                    copy.deepcopy(block),
                    (*path, *marker.path),
                    marker,
                    forms,
                    nested_blocks,
                )
                for index, (block, path, forms, nested_blocks) in enumerate(
                    _blocks(kind, depth, marker, marker_kind)
                )
            )
    return cases


@dataclass
class RandomBlock:
    """A block built at random, and the platform errors of the items put in it.

    The paths are the ones in the block as written.
    """

    kind: BlockKind
    submitted: Any = None
    platform_errors: list[tuple[Path, type[Exception] | None, str | None]] = field(
        default_factory=list
    )


def random_block(rng: random.Random, max_depth: int = 3) -> RandomBlock:
    """Return a block of valid and invalid items, in blocks nested at random.

    Unlike a block of the corpus, it can hold several invalid items.
    """
    result = RandomBlock(rng.choice(_KINDS))

    def leaf(kind: BlockKind, path: Path) -> Any:
        roll = rng.random()
        if roll < 0.5:
            return _OK[kind]
        if roll < 0.8:
            marker = rng.choice(PLATFORM_ERROR_MARKERS[kind])
            result.platform_errors.append(
                ((*path, *marker.path), marker.exception, marker.message)
            )
        else:
            marker = rng.choice(SCHEMA_ERROR_MARKERS[kind])
        return marker.item

    def item(kind: BlockKind, depth: int, path: Path) -> Any:
        nested_kinds = _NESTED_KINDS[kind]
        if depth == 0 or not nested_kinds or rng.random() < 0.4:
            return leaf(kind, path)
        nested_kind = rng.choice(nested_kinds)
        wrapper = rng.choice(_WRAPPERS[kind, nested_kind])
        built = wrapper.build(
            block(nested_kind, depth - 1, (*path, *wrapper.path), wrapper.only_list)
        )
        if rng.random() < 0.15:
            # An error of the item itself, next to the ones of its blocks
            built["bogus"] = 1
        return built

    def sublist(path: Path) -> Any:
        path = (*path, "triggers")
        if rng.random() < 0.3:
            return {"triggers": leaf("triggers", path)}
        return {
            "triggers": [
                leaf("triggers", (*path, index)) for index in range(rng.randint(0, 3))
            ]
        }

    def block(kind: BlockKind, depth: int, path: Path, only_list: bool = False) -> Any:
        if not only_list and rng.random() < 0.25:
            if kind == "triggers" and rng.random() < 0.4:
                return sublist(path)
            return item(kind, depth, path)
        return [
            sublist((*path, index))
            if kind == "triggers" and rng.random() < 0.35
            else item(kind, depth, (*path, index))
            for index in range(rng.randint(0, 3))
        ]

    # A copy, the items must not be shared
    result.submitted = copy.deepcopy(block(result.kind, rng.randint(0, max_depth), ()))
    return result
