"""Test collecting all validation errors of a block of triggers, conditions or actions."""

from collections.abc import Callable, Coroutine, Iterator
import copy
import gc
import logging
import random
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, Mock

import probatio
from probatio.markers import VirtualPathComponent
import pytest
from pytest_homeassistant.common import MockModule, mock_integration, mock_platform

from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition, script, trigger as trigger_helper
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.validation_errors import (
    ValidationErrorInfo,
    ValidationErrors,
    iter_validation_errors,
)

from .script_block_corpus import (
    OK_ACTION,
    OK_CONDITION,
    OK_TRIGGER,
    PARALLEL,
    PLATFORM_ERROR_MARKERS,
    REGISTRY_ID,
    SCHEMA_ERROR_MARKERS,
    SHORTHAND,
    SINGLE,
    SUBLIST,
    VALID_MARKERS,
    BlockKind,
    Case,
    Path,
    corpus,
    random_block,
)

# The path, the class and the message of an error
type Record = tuple[Path, type[Exception], str]

_BLOCK_VALIDATORS: dict[
    BlockKind, Callable[[HomeAssistant, list[Any]], Coroutine[Any, Any, list[Any]]]
] = {
    "triggers": trigger_helper.async_validate_trigger_config,
    "conditions": condition.async_validate_conditions_config,
    "actions": script.async_validate_actions_config,
}

_PLATFORM_ERROR_CORPUS = corpus(PLATFORM_ERROR_MARKERS)
_SCHEMA_ERROR_CORPUS = corpus(SCHEMA_ERROR_MARKERS)
_VALID_CORPUS = corpus(VALID_MARKERS)

_BAD_TRIGGER = {"alias": "No platform"}
_BAD_CONDITION = {"condition": "state", "entity_id": "light.kitchen"}
_BAD_ACTION = {"delay": 1, "bogus": 2}
_UNKNOWN_TRIGGER = {"trigger": "non_existing"}
_UNKNOWN_CONDITION = {"condition": "non_existing"}
_UNKNOWN_CONDITION_ERROR = 'Invalid condition "non_existing" specified'
_FIELD_TRIGGER = {"trigger": "numeric_state", "above": 1}
_FIELD_TRIGGER_ERROR = "required key not provided"
_REGISTRY_TRIGGER = {"trigger": "state", "entity_id": REGISTRY_ID}
_REGISTRY_CONDITION = {"condition": "state", "entity_id": REGISTRY_ID, "state": "on"}
_DEVICE_ACTION = {"device_id": "abc", "domain": "light", "type": "turn_on"}
_SERVICE_ACTION = {"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}}

_WALK_MISSED_ERROR = "one by one did not give the error of the block"

_RANDOM_BLOCKS = 250


def _grouped(cases: list[Case]) -> list[pytest.ParameterSet]:
    """Return a test parameter per group of cases of a corpus."""
    groups: dict[str, list[Case]] = {}
    for case in cases:
        groups.setdefault(case.group, []).append(case)
    return [pytest.param(group, id=name) for name, group in groups.items()]


def _records(err: probatio.Invalid | HomeAssistantError) -> list[Record]:
    """Return the errors in err."""
    return [
        (info.path, type(info.exception), info.message)
        for info in iter_validation_errors(err)
    ]


async def _async_collect(
    hass: HomeAssistant, kind: BlockKind, submitted: Any
) -> ValidationErrors:
    """Return the ValidationErrors raised for an invalid block."""
    block = copy.deepcopy(submitted)
    with pytest.raises(ValidationErrors) as exc_info:
        await script.async_validate_block_collect_errors(hass, kind, block)
    assert block == submitted
    return exc_info.value


async def _async_fail_fast(
    hass: HomeAssistant, kind: BlockKind, submitted: Any
) -> list[Any]:
    """Validate a block with its schema and its validator, which raise one error."""
    return await _BLOCK_VALIDATORS[kind](
        hass, script._BLOCK_SCHEMAS[kind](copy.deepcopy(submitted))
    )


async def _async_fail_fast_error(
    hass: HomeAssistant, kind: BlockKind, submitted: Any
) -> ValidationErrorInfo:
    """Return the error of the validator of a block which passes its schema."""
    validated = script._BLOCK_SCHEMAS[kind](copy.deepcopy(submitted))
    with pytest.raises((probatio.Invalid, HomeAssistantError)) as exc_info:
        await _BLOCK_VALIDATORS[kind](hass, validated)
    return next(iter_validation_errors(exc_info.value))


def _schema_error(kind: BlockKind, submitted: Any) -> probatio.Invalid:
    """Return the error of the schema of a block."""
    with pytest.raises(probatio.Invalid) as exc_info:
        script._BLOCK_SCHEMAS[kind](copy.deepcopy(submitted))
    return exc_info.value


def _schema_records(kind: BlockKind, submitted: Any) -> list[Record]:
    """Return the errors of the schema of a block, none if the block passes it."""
    try:
        script._BLOCK_SCHEMAS[kind](copy.deepcopy(submitted))
    except probatio.Invalid as err:
        return _records(err)
    return []


async def _async_fail_fast_records(
    hass: HomeAssistant, kind: BlockKind, submitted: Any
) -> list[Record]:
    """Return the first error of the schema and the validator of a block, if any."""
    try:
        await _async_fail_fast(hass, kind, submitted)
    except (probatio.Invalid, HomeAssistantError) as err:
        return _records(err)[:1]
    return []


async def _async_collected_records(
    hass: HomeAssistant, kind: BlockKind, submitted: Any
) -> list[Record]:
    """Return the errors collected for a block, none if the block is valid."""
    block = copy.deepcopy(submitted)
    records: list[Record] = []
    try:
        await script.async_validate_block_collect_errors(hass, kind, block)
    except ValidationErrors as err:
        records = _records(err)
    assert block == submitted
    return records


def _sorted_by_path(records: list[Record]) -> list[Record]:
    """Return errors sorted by their path."""
    return sorted(records, key=lambda record: [str(segment) for segment in record[0]])


def _device(number: int) -> dict[str, Any]:
    """Return a device action of an unknown device."""
    return {"device_id": f"device_{number}", "domain": "light", "type": "turn_on"}


def _device_trigger(number: int) -> dict[str, Any]:
    """Return a device trigger of an unknown device."""
    return {"trigger": "device", "device_id": f"device_{number}", "domain": "light"}


def _device_error(number: int, *path: str | int) -> Record:
    """Return the error of an unknown device."""
    return (path, InvalidDeviceAutomationConfig, f"Unknown device 'device_{number}'")


def _registry(number: int) -> dict[str, Any]:
    """Return a state condition of an unknown entity registry entry."""
    return {"condition": "state", "entity_id": f"{number:032x}", "state": "on"}


def _registry_trigger(number: int) -> dict[str, Any]:
    """Return a state trigger of an unknown entity registry entry."""
    return {"trigger": "state", "entity_id": f"{number:032x}"}


def _registry_error(number: int, *path: str | int) -> Record:
    """Return the error of an unknown entity registry entry."""
    return (path, probatio.Invalid, f"Unknown entity registry entry {number:032x}")


def _mock_trigger_platform(
    hass: HomeAssistant,
    validate: Callable[[HomeAssistant, ConfigType], Coroutine[Any, Any, ConfigType]],
) -> None:
    """Mock the trigger platform of the test integration."""
    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass,
        "test.trigger",
        Mock(
            spec=["async_validate_trigger_config"],
            async_validate_trigger_config=validate,
        ),
    )


@pytest.fixture
def trigger_errors(hass: HomeAssistant) -> dict[str, Exception]:
    """Mock a trigger platform which raises the error a trigger names."""
    errors: dict[str, Exception] = {
        "translated": HomeAssistantError(
            translation_domain="homeassistant",
            translation_key="service_not_found",
            translation_placeholders={"domain": "test", "service": "missing"},
        ),
        "untranslated": HomeAssistantError("Something is wrong"),
        "empty": probatio.MultipleInvalid([]),
        "other": ValueError("Not a validation error"),
    }

    async def async_validate_trigger_config(
        hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        if (error := config.get("error")) is not None:
            raise errors[error]
        return config

    _mock_trigger_platform(hass, async_validate_trigger_config)
    return errors


@pytest.fixture
def validate_trigger(hass: HomeAssistant) -> AsyncMock:
    """Mock a trigger platform, return its validator.

    It accepts every trigger. A test sets its side_effect to what it answers
    each time it is called: DEFAULT to accept the trigger, or an error.
    """
    validate = AsyncMock(side_effect=lambda hass, config: config)
    _mock_trigger_platform(hass, validate)
    return validate


def test_corpus_paths() -> None:
    """Test the path of each block of the corpus is the path of its marker."""

    def resolve(config: Any, path: Path) -> Any:
        for segment in path:
            config = config[segment]
        return config

    assert _PLATFORM_ERROR_CORPUS
    assert {
        case.id: resolve(case.submitted, case.marker_path)
        for case in _PLATFORM_ERROR_CORPUS
    } == {case.id: case.marker.item for case in _PLATFORM_ERROR_CORPUS}


@pytest.mark.parametrize(
    ("kind", "forms"),
    [
        pytest.param("triggers", {SINGLE, SUBLIST}, id="triggers"),
        pytest.param("conditions", {SINGLE, SHORTHAND}, id="conditions"),
        pytest.param("actions", {SINGLE, SUBLIST, SHORTHAND, PARALLEL}, id="actions"),
    ],
)
def test_corpus_forms(kind: BlockKind, forms: set[str]) -> None:
    """Test the corpus has every form a block of each kind can be written in."""
    assert {
        form
        for case in _PLATFORM_ERROR_CORPUS
        if case.kind == kind
        for form in case.forms
    } == forms


def _layout_blocks(layout: script._Layout) -> Iterator[tuple[str, BlockKind]]:
    """Yield the key and the kind of every block in a layout of nested blocks."""
    for key, nested in layout.items():
        if isinstance(nested, script._Block):
            yield key, nested.kind
        elif isinstance(nested, list):
            yield from _layout_blocks(nested[0])
        else:
            yield from _layout_blocks(nested)


def test_corpus_covers_nested_blocks() -> None:
    """Test every block of script._NESTED_BLOCKS is in the corpus.

    A block which is added to script._NESTED_BLOCKS must be added to the
    corpus too, to test the paths of the errors of its items.
    """
    nested_blocks = {
        (action_type, key): kind
        for action_type, layout in script._NESTED_BLOCKS.items()
        for key, kind in _layout_blocks(layout)
    }

    assert {
        nested_block
        for case in _PLATFORM_ERROR_CORPUS
        for nested_block in case.nested_blocks
    } == set(nested_blocks)
    # With each of the items which can be in the block
    assert {
        (nested_block, case.marker.name)
        for case in _PLATFORM_ERROR_CORPUS
        for nested_block in case.nested_blocks
    } >= {
        (nested_block, marker.name)
        for nested_block, kind in nested_blocks.items()
        for marker in PLATFORM_ERROR_MARKERS[kind]
    }


@pytest.mark.parametrize("cases", _grouped(_PLATFORM_ERROR_CORPUS))
async def test_platform_error_path_corpus(
    hass: HomeAssistant, cases: list[Case]
) -> None:
    """Test a platform error has its path in the block as written, in every form.

    The error is the one the validator of the block raises.
    """
    fail_fast = {}
    collected = {}
    expected = {}
    for case in cases:
        error = await _async_fail_fast_error(hass, case.kind, case.submitted)
        fail_fast[case.id] = (type(error.exception), error.message)
        err = await _async_collect(hass, case.kind, case.submitted)
        collected[case.id] = (case.submitted, _records(err), str(err))
        expected[case.id] = (
            case.submitted,
            [(case.path, case.marker.exception, case.marker.message)],
            str(ValidationErrorInfo(error.exception, case.path)),
        )

    assert fail_fast == {
        case.id: (case.marker.exception, case.marker.message) for case in cases
    }
    assert collected == expected


_MANY_ERRORS_ACTIONS = [
    _SERVICE_ACTION,
    _device(1),
    _registry(2),
    {
        "if": [OK_CONDITION, _registry(3)],
        "then": [_SERVICE_ACTION, _device(4)],
        "else": [_device(5)],
    },
    {
        "choose": [
            {
                "conditions": [_registry(6)],
                "sequence": [_device(7), _SERVICE_ACTION, _device(8)],
            }
        ],
        "default": [_device(9)],
    },
    {
        "parallel": [
            _device(10),
            [_SERVICE_ACTION, _device(11)],
            {"sequence": [_device(12)]},
        ]
    },
    {"repeat": {"until": [_registry(13)], "sequence": [_device(14)]}},
    {
        "wait_for_trigger": [
            OK_TRIGGER,
            _device_trigger(15),
            _device_trigger(16),
        ]
    },
    {
        "condition": "and",
        "conditions": [
            OK_CONDITION,
            _registry(17),
            {
                "condition": "or",
                "conditions": [
                    _registry(18),
                    {"condition": "not", "conditions": [_registry(19)]},
                ],
            },
        ],
    },
    *(
        item
        for number in range(20, 40, 2)
        for item in (_device(number), _registry(number + 1))
    ),
]
_MANY_ERRORS = [
    _device_error(1, 1),
    _registry_error(2, 2),
    _registry_error(3, 3, "if", 1),
    _device_error(4, 3, "then", 1),
    _device_error(5, 3, "else", 0),
    _device_error(9, 4, "default", 0),
    _registry_error(6, 4, "choose", 0, "conditions", 0),
    _device_error(7, 4, "choose", 0, "sequence", 0),
    _device_error(8, 4, "choose", 0, "sequence", 2),
    _device_error(10, 5, "parallel", 0),
    _device_error(11, 5, "parallel", 1, 1),
    _device_error(12, 5, "parallel", 2, "sequence", 0),
    _registry_error(13, 6, "repeat", "until", 0),
    _device_error(14, 6, "repeat", "sequence", 0),
    _device_error(15, 7, "wait_for_trigger", 1),
    _device_error(16, 7, "wait_for_trigger", 2),
    _registry_error(17, 8, "conditions", 1),
    _registry_error(18, 8, "conditions", 2, "conditions", 0),
    _registry_error(19, 8, "conditions", 2, "conditions", 1, "conditions", 0),
    *(
        error
        for index, number in enumerate(range(20, 40, 2))
        for error in (
            _device_error(number, 9 + 2 * index),
            _registry_error(number + 1, 10 + 2 * index),
        )
    ),
]

_ERRORS_PARAMS = [
    pytest.param(
        "triggers",
        [
            _registry_trigger(1),
            OK_TRIGGER,
            {"triggers": [_device_trigger(2), OK_TRIGGER, _registry_trigger(3)]},
            {"triggers": _registry_trigger(4)},
            _FIELD_TRIGGER,
        ],
        [
            _registry_error(1, 0),
            _device_error(2, 2, "triggers", 0),
            _registry_error(3, 2, "triggers", 2),
            _registry_error(4, 3, "triggers"),
            ((4, "entity_id"), probatio.RequiredFieldInvalid, _FIELD_TRIGGER_ERROR),
        ],
        id="triggers",
    ),
    pytest.param(
        "conditions",
        [
            _registry(1),
            {"and": [_registry(2), {"not": _registry(3)}]},
            {"condition": "or", "conditions": [OK_CONDITION, _registry(4)]},
            {"condition": [_registry(5)]},
            _UNKNOWN_CONDITION,
        ],
        [
            _registry_error(1, 0),
            _registry_error(2, 1, "and", 0),
            _registry_error(3, 1, "and", 1, "not"),
            _registry_error(4, 2, "conditions", 1),
            _registry_error(5, 3, "condition", 0),
            ((4,), HomeAssistantError, _UNKNOWN_CONDITION_ERROR),
        ],
        id="conditions",
    ),
    pytest.param(
        "conditions",
        [
            {
                "condition": "or",
                "conditions": [
                    {"and": [{"condition": "not", "conditions": _registry(1)}]}
                ],
            }
        ],
        [_registry_error(1, 0, "conditions", 0, "and", 0, "conditions")],
        id="condition_long_forms_and_shorthands",
    ),
    pytest.param(
        "actions",
        [_device(1), OK_ACTION, _registry(2), _device(3)],
        [_device_error(1, 0), _registry_error(2, 2), _device_error(3, 3)],
        id="actions",
    ),
    pytest.param(
        "actions",
        # The blocks of an action are validated in the order of
        # script._NESTED_BLOCKS, not in the order they are written in
        [
            {
                "else": [_device(4)],
                "then": [_device(3)],
                "if": [_registry(1), _registry(2)],
            }
        ],
        [
            _registry_error(1, 0, "if", 0),
            _registry_error(2, 0, "if", 1),
            _device_error(3, 0, "then", 0),
            _device_error(4, 0, "else", 0),
        ],
        id="if_then_else",
    ),
    pytest.param(
        "actions",
        [
            {
                "choose": [
                    {"sequence": [_device(3)], "conditions": [_registry(2)]},
                    {"conditions": [_registry(4)], "sequence": [_device(5)]},
                ],
                "default": [_device(1)],
            }
        ],
        [
            _device_error(1, 0, "default", 0),
            _registry_error(2, 0, "choose", 0, "conditions", 0),
            _device_error(3, 0, "choose", 0, "sequence", 0),
            _registry_error(4, 0, "choose", 1, "conditions", 0),
            _device_error(5, 0, "choose", 1, "sequence", 0),
        ],
        id="choose",
    ),
    pytest.param(
        "actions",
        [
            {
                "parallel": [
                    _device(1),
                    [OK_ACTION, _device(2), _device(3)],
                    {"sequence": [_device(4)]},
                    {"sequence": _device(5)},
                ]
            }
        ],
        [
            _device_error(1, 0, "parallel", 0),
            _device_error(2, 0, "parallel", 1, 1),
            _device_error(3, 0, "parallel", 1, 2),
            _device_error(4, 0, "parallel", 2, "sequence", 0),
            _device_error(5, 0, "parallel", 3, "sequence"),
        ],
        id="parallel",
    ),
    pytest.param(
        "actions",
        [{"parallel": [[{"parallel": [[_device(1)]]}]]}],
        [_device_error(1, 0, "parallel", 0, 0, "parallel", 0, 0)],
        id="parallel_list_branches_nested",
    ),
    pytest.param(
        "actions",
        [
            {
                "if": [{"or": [_registry(1), {"not": [_registry(2)]}]}],
                "then": [
                    {
                        "choose": {
                            "conditions": {"condition": [_registry(3)]},
                            "sequence": {
                                "parallel": [
                                    [_device(4), {"sequence": _device(5)}],
                                    {
                                        "wait_for_trigger": {
                                            "triggers": _registry_trigger(6)
                                        }
                                    },
                                ]
                            },
                        }
                    },
                    _device(7),
                ],
            },
            _device(8),
        ],
        [
            _registry_error(1, 0, "if", 0, "or", 0),
            _registry_error(2, 0, "if", 0, "or", 1, "not", 0),
            _registry_error(3, 0, "then", 0, "choose", "conditions", "condition", 0),
            _device_error(4, 0, "then", 0, "choose", "sequence", "parallel", 0, 0),
            _device_error(
                5, 0, "then", 0, "choose", "sequence", "parallel", 0, 1, "sequence"
            ),
            _registry_error(
                6,
                *(0, "then", 0, "choose", "sequence", "parallel", 1),
                *("wait_for_trigger", "triggers"),
            ),
            _device_error(7, 0, "then", 1),
            _device_error(8, 1),
        ],
        id="nested",
    ),
    pytest.param(
        "actions",
        {
            "if": [],
            "then": {
                "choose": {
                    "conditions": {"not": OK_CONDITION},
                    "sequence": {
                        "repeat": {
                            "count": 2,
                            "sequence": {
                                "parallel": [
                                    [
                                        {
                                            "sequence": {
                                                "if": [],
                                                "then": [],
                                                "else": {
                                                    "wait_for_trigger": {
                                                        "triggers": [
                                                            OK_TRIGGER,
                                                            _registry_trigger(1),
                                                        ]
                                                    }
                                                },
                                            }
                                        }
                                    ]
                                ]
                            },
                        }
                    },
                }
            },
        },
        [
            _registry_error(
                1,
                "then",
                *("choose", "sequence"),
                *("repeat", "sequence"),
                *("parallel", 0, 0),
                "sequence",
                "else",
                *("wait_for_trigger", "triggers", 1),
            )
        ],
        id="nested_single_items",
    ),
    pytest.param("actions", _MANY_ERRORS_ACTIONS, _MANY_ERRORS, id="many_errors"),
]


@pytest.mark.parametrize(("kind", "submitted", "expected"), _ERRORS_PARAMS)
async def test_all_errors_in_validation_order(
    hass: HomeAssistant, kind: BlockKind, submitted: Any, expected: list[Record]
) -> None:
    """Test all platform errors of a block are collected, in validation order.

    The first error is the one the validator of the block raises.
    """
    fail_fast = await _async_fail_fast_error(hass, kind, submitted)

    err = await _async_collect(hass, kind, submitted)

    assert _records(err) == expected
    assert (type(fail_fast.exception), fail_fast.message) == expected[0][1:]
    assert str(err) == str(ValidationErrorInfo(fail_fast.exception, expected[0][0]))


async def test_all_errors_of_an_item(hass: HomeAssistant) -> None:
    """Test all errors of one item are collected, in the order they are raised in."""
    invalid_trigger = {"trigger": "numeric_state", "above": "x", "below": "y"}
    with pytest.raises(probatio.MultipleInvalid) as exc_info:
        await _async_fail_fast(hass, "triggers", [invalid_trigger])
    item_errors = [
        (path[1:], error_class, message)
        for path, error_class, message in _records(exc_info.value)
    ]
    assert sorted(path for path, _, _ in item_errors) == [
        ("above",),
        ("below",),
        ("entity_id",),
    ]

    err = await _async_collect(
        hass,
        "triggers",
        [_registry_trigger(1), {"triggers": [invalid_trigger]}, _registry_trigger(2)],
    )

    assert _records(err) == [
        _registry_error(1, 0),
        *(
            ((1, "triggers", 0, *path), error_class, message)
            for path, error_class, message in item_errors
        ),
        _registry_error(2, 2),
    ]


@pytest.mark.parametrize("cases", _grouped(_VALID_CORPUS))
async def test_valid_block_corpus(hass: HomeAssistant, cases: list[Case]) -> None:
    """Test a valid block gives the validated block, in every form."""
    expected = {
        case.id: await _async_fail_fast(hass, case.kind, case.submitted)
        for case in cases
    }

    assert {
        case.id: await script.async_validate_block_collect_errors(
            hass, case.kind, copy.deepcopy(case.submitted)
        )
        for case in cases
    } == expected


@pytest.mark.parametrize(
    ("kind", "submitted"),
    [
        pytest.param("triggers", None, id="no_triggers"),
        pytest.param("triggers", [], id="empty_triggers"),
        pytest.param("triggers", {"triggers": []}, id="empty_sublist"),
        pytest.param("conditions", None, id="no_conditions"),
        pytest.param("conditions", "{{ true }}", id="template_condition"),
        pytest.param("conditions", ["{{ true }}", {"or": []}], id="template_in_list"),
        pytest.param("actions", None, id="no_actions"),
        pytest.param("actions", [], id="empty_actions"),
        pytest.param(
            "actions",
            [
                _SERVICE_ACTION,
                {"delay": "00:00:05"},
                {"if": "{{ true }}", "then": {"stop": "done"}},
                {"choose": [], "default": {"event": "test_event"}},
                {
                    "parallel": [
                        {"delay": 1},
                        [{"delay": 2}],
                        {"sequence": {"delay": 3}},
                    ]
                },
                {"repeat": {"for_each": [1, 2], "sequence": OK_ACTION}},
                {"wait_for_trigger": {"triggers": OK_TRIGGER}, "timeout": 5},
            ],
            id="actions",
        ),
    ],
)
async def test_valid_block(
    hass: HomeAssistant, kind: BlockKind, submitted: Any
) -> None:
    """Test a valid block gives the validated block, and is not changed."""
    expected = await _async_fail_fast(hass, kind, submitted)
    block = copy.deepcopy(submitted)

    assert (
        await script.async_validate_block_collect_errors(hass, kind, block) == expected
    )
    assert block == submitted


async def test_valid_block_is_validated_once(
    hass: HomeAssistant, validate_trigger: AsyncMock
) -> None:
    """Test the platforms validate the items of a valid block only once."""
    submitted = [{"trigger": "test"}, {"triggers": {"trigger": "test", "id": "2"}}]

    assert await script.async_validate_block_collect_errors(
        hass, "triggers", submitted
    ) == [{"platform": "test"}, {"platform": "test", "id": "2"}]
    assert validate_trigger.await_count == 2


@pytest.mark.parametrize("cases", _grouped(_SCHEMA_ERROR_CORPUS))
async def test_schema_error_corpus(hass: HomeAssistant, cases: list[Case]) -> None:
    """Test the error of a schema is collected as it is, in every form."""
    schema_paths = {}
    collected = {}
    expected = {}
    for case in cases:
        schema_error = _schema_error(case.kind, case.submitted)
        schema_paths[case.id] = [path for path, _, _ in _records(schema_error)]
        expected[case.id] = (_records(schema_error), str(schema_error))
        err = await _async_collect(hass, case.kind, case.submitted)
        collected[case.id] = (_records(err), str(err))

    # The schemas give the path in the block as written
    assert schema_paths == {case.id: [case.path] for case in cases}
    assert collected == expected


@pytest.mark.parametrize(
    ("kind", "submitted", "expected_paths"),
    [
        pytest.param(
            "actions",
            [_BAD_ACTION, OK_ACTION, {"if": []}, {"event": "x", "bogus": 1}],
            [(0, "bogus"), (2, "then"), (3, "bogus")],
            id="several_errors",
        ),
        pytest.param("actions", 5, [()], id="not_an_action"),
    ],
)
async def test_schema_error(
    hass: HomeAssistant, kind: BlockKind, submitted: Any, expected_paths: list[Path]
) -> None:
    """Test the errors of the schema of a block are collected as they are."""
    schema_error = _schema_error(kind, submitted)

    err = await _async_collect(hass, kind, submitted)

    assert [info.path for info in err.errors] == expected_paths
    assert _records(err) == _records(schema_error)
    assert str(err) == str(schema_error)


@pytest.mark.parametrize(
    ("kind", "submitted", "schema_paths", "platform_paths"),
    [
        pytest.param(
            "conditions",
            [_BAD_CONDITION, _UNKNOWN_CONDITION, _REGISTRY_CONDITION],
            [(0, "state")],
            [(1,), (2,)],
            id="conditions",
        ),
        pytest.param(
            "conditions",
            [
                {
                    "or": [
                        {
                            "and": [
                                OK_CONDITION,
                                {"not": [_BAD_CONDITION]},
                                _UNKNOWN_CONDITION,
                            ]
                        },
                        _UNKNOWN_CONDITION,
                        {"not": _REGISTRY_CONDITION},
                    ]
                }
            ],
            [(0, "or", 0, "and", 1, "not", 0, "state")],
            [(0, "or", 0, "and", 2), (0, "or", 1), (0, "or", 2, "not")],
            id="shorthands_nested",
        ),
        pytest.param(
            "conditions",
            [{"or": [_UNKNOWN_CONDITION], "bogus": 1}],
            [(0, "bogus")],
            [(0, "or", 0)],
            id="shorthand_with_error_of_its_own",
        ),
        pytest.param(
            "actions",
            [_BAD_ACTION, _DEVICE_ACTION],
            [(0, "bogus")],
            [(1,)],
            id="actions",
        ),
        pytest.param(
            "actions",
            [{"if": [_UNKNOWN_CONDITION], "then": [_DEVICE_ACTION], "bogus": 1}],
            [(0, "bogus")],
            [(0, "if", 0), (0, "then", 0)],
            id="if_with_error_of_its_own",
        ),
        pytest.param(
            "actions",
            [{"if": [_UNKNOWN_CONDITION]}, _DEVICE_ACTION],
            [(0, "then")],
            [(0, "if", 0), (1,)],
            id="if_without_then",
        ),
        pytest.param(
            "actions",
            [
                {
                    "choose": [
                        {
                            "conditions": [_UNKNOWN_CONDITION],
                            "sequence": [_DEVICE_ACTION],
                            "bogus": 1,
                        }
                    ]
                }
            ],
            [(0, "choose", 0, "bogus")],
            [(0, "choose", 0, "conditions", 0), (0, "choose", 0, "sequence", 0)],
            id="choose_option_with_error_of_its_own",
        ),
        pytest.param(
            "actions",
            [
                {
                    "parallel": [
                        _DEVICE_ACTION,
                        [_BAD_ACTION, _DEVICE_ACTION],
                        {"sequence": [_BAD_ACTION, _DEVICE_ACTION]},
                        {"sequence": _DEVICE_ACTION},
                        _BAD_ACTION,
                    ]
                }
            ],
            [
                (0, "parallel", 1, 0, "bogus"),
                (0, "parallel", 2, "sequence", 0, "bogus"),
                (0, "parallel", 4, "bogus"),
            ],
            [
                (0, "parallel", 0),
                (0, "parallel", 1, 1),
                (0, "parallel", 2, "sequence", 1),
                (0, "parallel", 3, "sequence"),
            ],
            id="parallel",
        ),
        pytest.param(
            "actions",
            [
                {
                    "if": [_UNKNOWN_CONDITION],
                    "then": [
                        {
                            "choose": [
                                {
                                    "conditions": [_REGISTRY_CONDITION],
                                    "sequence": [_BAD_ACTION, _DEVICE_ACTION],
                                }
                            ]
                        }
                    ],
                    "else": [_DEVICE_ACTION],
                },
                _DEVICE_ACTION,
            ],
            [(0, "then", 0, "choose", 0, "sequence", 0, "bogus")],
            [
                (0, "if", 0),
                (0, "then", 0, "choose", 0, "conditions", 0),
                (0, "then", 0, "choose", 0, "sequence", 1),
                (0, "else", 0),
                (1,),
            ],
            id="platform_errors_at_every_level",
        ),
        pytest.param(
            "actions",
            [
                {
                    "parallel": [
                        {
                            "wait_for_trigger": [
                                _BAD_TRIGGER,
                                {"triggers": [_UNKNOWN_TRIGGER]},
                            ]
                        },
                        [
                            _DEVICE_ACTION,
                            {
                                "repeat": {
                                    "while": [_UNKNOWN_CONDITION],
                                    "sequence": [_BAD_ACTION],
                                }
                            },
                        ],
                    ]
                }
            ],
            [
                (0, "parallel", 0, "wait_for_trigger", 0, "trigger"),
                (0, "parallel", 1, 1, "repeat", "sequence", 0, "bogus"),
            ],
            [
                (0, "parallel", 0, "wait_for_trigger", 1, "triggers", 0),
                (0, "parallel", 1, 0),
                (0, "parallel", 1, 1, "repeat", "while", 0),
            ],
            id="both_kinds_of_errors_in_nested_blocks",
        ),
        pytest.param(
            "triggers",
            [
                {"triggers": [_UNKNOWN_TRIGGER, _BAD_TRIGGER]},
                _UNKNOWN_TRIGGER,
                {"triggers": _UNKNOWN_TRIGGER},
            ],
            [(0, "triggers", 1, "trigger")],
            [(0, "triggers", 0), (1,), (2, "triggers")],
            id="trigger_sublists",
        ),
        pytest.param(
            "triggers",
            [5, _UNKNOWN_TRIGGER],
            [(0,)],
            [(1,)],
            id="trigger_not_a_dict",
        ),
        # A sublist can't hold a sublist: the inner one is an invalid trigger,
        # and the trigger in it is not an item of the block
        pytest.param(
            "triggers",
            [{"triggers": [{"triggers": [_UNKNOWN_TRIGGER]}]}, _UNKNOWN_TRIGGER],
            [(0, "triggers", 0, "trigger")],
            [(1,)],
            id="trigger_sublist_in_sublist",
        ),
        # The items of a condition are conditions, also in a block of actions
        pytest.param(
            "actions",
            [{"and": [_DEVICE_ACTION]}, _DEVICE_ACTION],
            [(0, "and", 0)],
            [(1,)],
            id="action_in_condition_action",
        ),
        # Only an and, or or not condition holds conditions
        pytest.param(
            "conditions",
            [
                {
                    "condition": "state",
                    "entity_id": "light.kitchen",
                    "state": "on",
                    "conditions": [_UNKNOWN_CONDITION],
                },
                _UNKNOWN_CONDITION,
            ],
            [(0, "conditions")],
            [(1,)],
            id="conditions_in_other_condition",
        ),
        # Only a condition holds conditions: here and is an extra key of the
        # delay action, and the condition below it is not an item of the block
        pytest.param(
            "actions",
            [{"delay": 1, "and": [_UNKNOWN_CONDITION]}, _DEVICE_ACTION],
            [(0, "and")],
            [(1,)],
            id="conditions_in_other_action",
        ),
    ],
)
async def test_schema_and_platform_errors(
    hass: HomeAssistant,
    kind: BlockKind,
    submitted: Any,
    schema_paths: list[Path],
    platform_paths: list[Path],
) -> None:
    """Test the platform errors of the items which pass their schema are collected.

    They follow the errors of the schema of the block, in validation order.
    """
    schema_error = _schema_error(kind, submitted)

    err = await _async_collect(hass, kind, submitted)

    assert [info.path for info in err.errors] == [*schema_paths, *platform_paths]
    assert _records(err)[: len(schema_paths)] == _records(schema_error)
    assert str(err) == str(schema_error)


@pytest.mark.parametrize(
    "seed", [pytest.param(seed, id=f"seed_{seed}") for seed in range(4)]
)
async def test_random_blocks(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, seed: int
) -> None:
    """Test random blocks give the errors of their schema and of the items in them.

    This guards shapes the corpus doesn't enumerate: several errors in one
    block, and blocks nested deeper.
    """
    rng = random.Random(seed)
    collected = {}
    expected = {}
    for index in range(_RANDOM_BLOCKS):
        block = random_block(rng)
        schema_records = _schema_records(block.kind, block.submitted)
        fail_fast = await _async_fail_fast_records(hass, block.kind, block.submitted)
        records = await _async_collected_records(hass, block.kind, block.submitted)
        collected[index] = (
            block.submitted,
            records[: len(schema_records)],
            _sorted_by_path(records[len(schema_records) :]),
            [(error_class, message) for _, error_class, message in records[:1]],
        )
        expected[index] = (
            block.submitted,
            schema_records,
            _sorted_by_path(block.platform_errors),
            # The first error is the one the schema or the validator raises
            [(error_class, message) for _, error_class, message in fail_fast],
        )

    assert collected == expected
    assert _WALK_MISSED_ERROR not in caplog.text


async def test_schema_and_platform_error_classes(hass: HomeAssistant) -> None:
    """Test schema errors and platform errors are collected as they are raised."""
    err = await _async_collect(
        hass,
        "actions",
        [
            _DEVICE_ACTION,
            _BAD_ACTION,
            {"or": [_REGISTRY_CONDITION]},
            OK_ACTION,
            {"if": [_UNKNOWN_CONDITION], "then": []},
        ],
    )

    assert _records(err) == [
        ((1, "bogus"), probatio.ExtraKeysInvalid, "not a valid option"),
        ((0,), InvalidDeviceAutomationConfig, "Unknown device 'abc'"),
        (
            (2, "or", 0),
            probatio.Invalid,
            f"Unknown entity registry entry {REGISTRY_ID}",
        ),
        ((4, "if", 0), HomeAssistantError, _UNKNOWN_CONDITION_ERROR),
    ]
    assert str(err) == "not a valid option at '[1].bogus'"


@pytest.mark.parametrize(
    ("kind", "submitted"),
    [
        pytest.param(
            "triggers",
            [{"triggers": [_REGISTRY_TRIGGER], "alias": "Not a sublist"}],
            id="sublist_with_other_keys",
        ),
        pytest.param("triggers", [[_REGISTRY_TRIGGER]], id="list_in_trigger_list"),
        pytest.param("triggers", (_REGISTRY_TRIGGER,), id="tuple_of_triggers"),
        pytest.param(
            "conditions", [[_REGISTRY_CONDITION]], id="list_in_condition_list"
        ),
        pytest.param(
            "actions",
            [{"delay": 1, "sequence": [_REGISTRY_CONDITION]}],
            id="sequence_in_delay",
        ),
        pytest.param(
            "actions",
            [{"event": "test", "wait_for_trigger": [_REGISTRY_TRIGGER]}],
            id="triggers_in_event",
        ),
        pytest.param(
            "actions", [{"unknown": [_REGISTRY_CONDITION]}], id="not_an_action"
        ),
    ],
)
async def test_only_items_of_the_schema_are_validated_by_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    kind: BlockKind,
    submitted: Any,
) -> None:
    """Test what the schema does not take for an item gets no platform error."""
    assert _records(await _async_collect(hass, kind, submitted)) == _records(
        _schema_error(kind, submitted)
    )
    assert _WALK_MISSED_ERROR not in caplog.text


@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param(5, id="int"),
        pytest.param("text", id="str"),
        pytest.param([OK_ACTION], id="list"),
        pytest.param({}, id="empty"),
        pytest.param({"choose": 5}, id="choose_int"),
        pytest.param({"choose": [5]}, id="choose_option_int"),
        pytest.param({"choose": [[]]}, id="choose_option_list"),
        pytest.param({"choose": {"conditions": 5}}, id="choose_conditions_int"),
        pytest.param({"choose": [], "default": 5}, id="default_int"),
        pytest.param({"if": 5, "then": "text"}, id="if_int"),
        pytest.param({"if": {"and": 5}, "then": []}, id="and_int"),
        pytest.param({"if": {"condition": [5]}, "then": []}, id="condition_list_int"),
        pytest.param({"repeat": 5}, id="repeat_int"),
        pytest.param({"repeat": [OK_ACTION]}, id="repeat_list"),
        pytest.param({"repeat": {"count": 1, "sequence": 5}}, id="repeat_sequence_int"),
        pytest.param({"parallel": 5}, id="parallel_int"),
        pytest.param({"parallel": [[5]]}, id="parallel_branch_int"),
        pytest.param({"parallel": {"sequence": 5}}, id="parallel_sequence_int"),
        pytest.param({"sequence": {"sequence": 5}}, id="sequence_int"),
        pytest.param({"wait_for_trigger": 5}, id="wait_for_trigger_int"),
        pytest.param({"wait_for_trigger": {"triggers": 5}}, id="sublist_int"),
        pytest.param({"wait_for_trigger": [[5]]}, id="trigger_list"),
    ],
)
async def test_platform_errors_next_to_malformed_item(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, invalid: Any
) -> None:
    """Test the errors of valid items are collected next to an item of any shape."""
    submitted = [invalid, {"if": [_REGISTRY_CONDITION], "then": []}]

    err = await _async_collect(hass, "actions", submitted)

    assert [info.path for info in err.errors] == [
        *(path for path, _, _ in _records(_schema_error("actions", submitted))),
        (1, "if", 0),
    ]
    assert _WALK_MISSED_ERROR not in caplog.text


@pytest.mark.parametrize(
    ("kind", "submitted", "error", "expected_error"),
    [
        pytest.param(
            "triggers",
            [OK_TRIGGER, {"trigger": "test", "error": "untranslated"}],
            "untranslated",
            "Something is wrong at '[1]'",
            id="homeassistant_error",
        ),
        pytest.param(
            "triggers",
            {"triggers": [OK_TRIGGER, {"trigger": "test", "error": "translated"}]},
            "translated",
            "Action test.missing not found at 'triggers[1]'",
            id="translated_homeassistant_error",
        ),
        pytest.param(
            "triggers",
            [OK_TRIGGER, {"trigger": "test", "error": "empty"}, OK_TRIGGER],
            "empty",
            "no validation errors at '[1]'",
            id="empty_multiple_invalid",
        ),
        pytest.param(
            "actions",
            [{"parallel": {"wait_for_trigger": {"trigger": "test", "error": "empty"}}}],
            "empty",
            "no validation errors at '[0].parallel.wait_for_trigger'",
            id="empty_multiple_invalid_nested",
        ),
    ],
)
async def test_error_kinds(
    hass: HomeAssistant,
    trigger_errors: dict[str, Exception],
    kind: BlockKind,
    submitted: Any,
    error: str,
    expected_error: str,
) -> None:
    """Test each kind of error a platform can raise is collected as it is."""
    err = await _async_collect(hass, kind, submitted)

    assert [info.exception for info in err.errors] == [trigger_errors[error]]
    assert str(err) == expected_error


async def test_several_error_kinds(
    hass: HomeAssistant, trigger_errors: dict[str, Exception]
) -> None:
    """Test errors of different kinds are collected together."""
    err = await _async_collect(
        hass,
        "triggers",
        [
            {"trigger": "test", "error": "empty"},
            {"trigger": "test"},
            {"trigger": "test", "error": "translated"},
            _registry_trigger(1),
            {"trigger": "test", "error": "untranslated"},
        ],
    )

    assert err.errors[0].exception is trigger_errors["empty"]
    assert err.errors[1].exception is trigger_errors["translated"]
    assert err.errors[3].exception is trigger_errors["untranslated"]
    assert _records(err) == [
        ((0,), probatio.MultipleInvalid, "no validation errors"),
        ((2,), HomeAssistantError, "Action test.missing not found"),
        _registry_error(1, 3),
        ((4,), HomeAssistantError, "Something is wrong"),
    ]


@pytest.mark.parametrize(
    "submitted",
    [
        pytest.param([{"trigger": "test", "error": "other"}], id="only_error"),
        pytest.param(
            [{"trigger": "test", "error": "other"}, _registry_trigger(1)],
            id="first_error",
        ),
        pytest.param(
            [_BAD_TRIGGER, {"trigger": "test", "error": "other"}],
            id="after_schema_error",
        ),
    ],
)
@pytest.mark.usefixtures("trigger_errors")
async def test_other_exceptions_are_not_collected(
    hass: HomeAssistant, submitted: list[dict[str, Any]]
) -> None:
    """Test an exception which is not a validation error is raised as it is."""
    with pytest.raises(ValueError, match="Not a validation error"):
        await script.async_validate_block_collect_errors(hass, "triggers", submitted)


@pytest.mark.parametrize(
    ("kind", "submitted", "expected_path"),
    [
        pytest.param(
            "triggers",
            [
                OK_TRIGGER,
                {
                    "trigger": "state",
                    "entity_id": "light.kitchen",
                    "to": "on",
                    "not_to": "off",
                },
            ],
            (1, "to"),
            id="platform_error",
        ),
        pytest.param(
            "actions",
            {"repeat": {"count": 2, "while": [], "sequence": []}},
            ("repeat", "repeat"),
            id="schema_error",
        ),
    ],
)
async def test_group_segment(
    hass: HomeAssistant, kind: BlockKind, submitted: Any, expected_path: Path
) -> None:
    """Test the path of an error keeps the group the error is about."""
    err = await _async_collect(hass, kind, submitted)

    assert [info.path for info in err.errors] == [expected_path]
    assert type(err.errors[0].path[-1]) is VirtualPathComponent


async def test_path_segments_are_not_converted(hass: HomeAssistant) -> None:
    """Test the segments of the path of an error are the ones the platform gives."""
    fail_fast = await _async_fail_fast_error(hass, "triggers", [_FIELD_TRIGGER])
    assert type(fail_fast.path[-1]) is not str

    err = await _async_collect(hass, "triggers", {"triggers": _FIELD_TRIGGER})

    assert err.errors[0].path == ("triggers", "entity_id")
    assert type(err.errors[0].path[-1]) is type(fail_fast.path[-1])


@pytest.mark.parametrize(
    ("kind", "submitted"),
    [
        pytest.param(
            "actions", [_SERVICE_ACTION, _device(1)], id="homeassistant_error"
        ),
        pytest.param("actions", [_SERVICE_ACTION, _registry(1)], id="invalid"),
        pytest.param(
            "triggers",
            {"triggers": [OK_TRIGGER, _FIELD_TRIGGER]},
            id="multiple_invalid",
        ),
        pytest.param(
            "triggers",
            [_FIELD_TRIGGER, _device_trigger(1)],
            id="multiple_invalid_and_other_error",
        ),
        pytest.param(
            "actions",
            [{"if": [_registry(1)], "then": {"parallel": _device(2)}}, _device(3)],
            id="several_errors",
        ),
        pytest.param("actions", _MANY_ERRORS_ACTIONS, id="many_errors"),
    ],
)
async def test_no_reference_cycles(
    hass: HomeAssistant, kind: BlockKind, submitted: Any
) -> None:
    """Test collecting platform errors leaves nothing for the garbage collector.

    The blocks are ones for which the schemas and the validators leave nothing.
    Some schemas leave reference cycles of their own, for example the one of a
    delay action.
    """

    async def fail_fast(block: Any) -> None:
        await _BLOCK_VALIDATORS[kind](hass, script._BLOCK_SCHEMAS[kind](block))

    async def collect(block: Any) -> None:
        await script.async_validate_block_collect_errors(hass, kind, block)

    async def unreachable_objects(
        validate: Callable[[Any], Coroutine[Any, Any, None]],
    ) -> tuple[int, int]:
        failures = 0
        blocks = [copy.deepcopy(submitted) for _ in range(200)]
        gc.collect()
        gc.disable()
        try:
            for block in blocks:
                try:
                    await validate(block)
                except probatio.Invalid, HomeAssistantError:
                    failures += 1
            return failures, gc.collect()
        finally:
            gc.enable()

    # Load the platforms, and let probatio compile the schemas: it replaces a
    # schema after 50 calls, which leaves a reference cycle once
    await unreachable_objects(fail_fast)
    await unreachable_objects(collect)

    assert await unreachable_objects(fail_fast) == (200, 0)
    assert await unreachable_objects(collect) == (200, 0)


def _trigger_failed(message: str = "Trigger failed") -> probatio.Invalid:
    """Return the error of a mocked trigger platform."""
    return probatio.Invalid(message, path=["fail"])


async def test_error_of_the_block_is_collected_once(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, validate_trigger: AsyncMock
) -> None:
    """Test the error the validator of the block raises is not collected twice."""
    submitted = [
        {"trigger": "test"},
        {"triggers": [{"trigger": "test"}, {"trigger": "test"}]},
    ]
    validate_trigger.side_effect = [
        # The validator of the block stops at its first error
        *(DEFAULT, _trigger_failed()),
        *(DEFAULT, _trigger_failed(), _trigger_failed()),
    ]

    err = await _async_collect(hass, "triggers", submitted)

    assert [info.path for info in err.errors] == [
        (1, "triggers", 0, "fail"),
        (1, "triggers", 1, "fail"),
    ]
    assert _WALK_MISSED_ERROR not in caplog.text


@pytest.mark.parametrize(
    ("answers", "errors", "text"),
    [
        pytest.param(
            [DEFAULT, _trigger_failed(), DEFAULT, DEFAULT],
            [((0, "wait_for_trigger", 1, "fail"), "Trigger failed")],
            "Trigger failed at '[0].wait_for_trigger[1].fail'",
            id="invalid",
        ),
        pytest.param(
            [DEFAULT, HomeAssistantError("Trigger failed"), DEFAULT, DEFAULT],
            [((), "Trigger failed")],
            "Trigger failed",
            id="homeassistant_error",
        ),
        pytest.param(
            [_trigger_failed("Failed once"), DEFAULT, _trigger_failed()],
            [
                ((0, "wait_for_trigger", 0, "fail"), "Failed once"),
                (("wait_for_trigger", 0, "triggers", 1, "fail"), "Trigger failed"),
            ],
            "Failed once at '[0].wait_for_trigger[0].fail'",
            id="invalid_and_other_error",
        ),
        pytest.param(
            [HomeAssistantError("Failed once"), DEFAULT, _trigger_failed()],
            [
                ((), "Failed once"),
                (("wait_for_trigger", 0, "triggers", 1, "fail"), "Trigger failed"),
            ],
            "Failed once",
            id="homeassistant_error_and_other_error",
        ),
        pytest.param(
            [HomeAssistantError("Trigger failed"), _trigger_failed(), DEFAULT],
            [
                ((), "Trigger failed"),
                (("wait_for_trigger", 0, "triggers", 0, "fail"), "Trigger failed"),
            ],
            "Trigger failed",
            id="same_message_other_class",
        ),
        pytest.param(
            [
                *(DEFAULT, _trigger_failed()),
                *(_trigger_failed("Failed later"), _trigger_failed()),
            ],
            [
                ((0, "wait_for_trigger", 1, "fail"), "Trigger failed"),
                (("wait_for_trigger", 0, "triggers", 0, "fail"), "Failed later"),
                (("wait_for_trigger", 0, "triggers", 1, "fail"), "Trigger failed"),
            ],
            "Trigger failed at '[0].wait_for_trigger[1].fail'",
            id="same_error_not_first",
        ),
    ],
)
async def test_error_of_the_block_is_kept_if_its_item_is_not_found(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    validate_trigger: AsyncMock,
    answers: list[Any],
    errors: list[tuple[Path, str]],
    text: str,
) -> None:
    """Test the error of the block is logged and comes first if no item gives it.

    Here the platform does not answer the same when the items are validated
    one by one, so the first error it gives then is not the error of the
    block. The path of the error of the block is then not the one in the block
    as written. For a probatio.Invalid it is the one in the validated block:
    the action is in a list, and the sublist of triggers is flattened. A
    HomeAssistantError has no path.
    """
    submitted = {
        "wait_for_trigger": [{"triggers": [{"trigger": "test"}, {"trigger": "test"}]}]
    }
    # The answers to the validator of the block, which stops at its first
    # error, followed by the answers for each of the two triggers
    validate_trigger.side_effect = answers

    err = await _async_collect(hass, "actions", submitted)

    assert [(info.path, info.message) for info in err.errors] == errors
    assert str(err) == text
    assert caplog.record_tuples == [
        (
            "homeassistant.helpers.script",
            logging.WARNING,
            f"Validating the items of a block of actions {_WALK_MISSED_ERROR}: {text}",
        )
    ]
