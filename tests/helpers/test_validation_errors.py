"""Test the helpers to collect, locate and serialize config validation errors."""

from datetime import timedelta
from enum import StrEnum
import gc
import threading
from typing import Any

import probatio
from probatio.markers import VirtualPathComponent
import pytest

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.validation_errors import (
    ValidationErrorInfo,
    ValidationErrors,
    iter_validation_errors,
    validation_errors_as_dicts,
)


class _Key(StrEnum):
    """A key of a config."""

    NAME = "name"


class _Unserializable:
    """An object which can't be serialized to JSON."""

    def __repr__(self) -> str:
        """Return the representation."""
        return "<unserializable>"


def _raised[_ExceptionT: Exception](err: _ExceptionT) -> _ExceptionT:
    """Return an exception which was raised, so it has a traceback."""
    try:
        raise err
    except type(err) as raised:
        return raised


def test_iter_validation_errors_invalid() -> None:
    """Test a probatio.Invalid gives one record, below the path."""
    err = _raised(probatio.RequiredFieldInvalid("required key not provided", ["a", 1]))

    records = list(iter_validation_errors(err, ["actions", 0]))

    assert records == [ValidationErrorInfo(err, ("actions", 0, "a", 1))]
    assert records[0].exception is err
    assert records[0].message == "required key not provided"
    assert str(records[0]) == "required key not provided at 'actions[0].a[1]'"
    # The error is not changed, apart from its traceback
    assert err.path == ["a", 1]
    assert err.__traceback__ is None


def test_iter_validation_errors_multiple_invalid() -> None:
    """Test a MultipleInvalid is flattened, also when nested."""
    first = probatio.Invalid("first", ["a"])
    second = probatio.ExtraKeysInvalid("second", ["b", "c"])
    third = probatio.Invalid("third")
    err = probatio.MultipleInvalid([first, probatio.MultipleInvalid([second, third])])

    assert list(iter_validation_errors(err, [2])) == [
        ValidationErrorInfo(first, (2, "a")),
        ValidationErrorInfo(second, (2, "b", "c")),
        ValidationErrorInfo(third, (2,)),
    ]


def test_iter_validation_errors_empty_multiple_invalid() -> None:
    """Test a MultipleInvalid without errors gives one record."""
    err = _raised(probatio.MultipleInvalid([]))

    records = list(iter_validation_errors(err, [1]))

    assert records == [ValidationErrorInfo(err, (1,))]
    assert records[0].message == "no validation errors"
    assert str(records[0]) == "no validation errors at '[1]'"
    assert err.__traceback__ is None
    assert validation_errors_as_dicts(ValidationErrors(records)) == [
        {
            "message": "no validation errors",
            "path": [1],
            "code": None,
            "translation_key": None,
            "translation_domain": None,
            "translation_placeholders": {},
        }
    ]


def test_iter_validation_errors_homeassistant_error() -> None:
    """Test a HomeAssistantError gives one record, at the path."""
    err = _raised(HomeAssistantError("Unknown device 'abc'"))

    records = list(iter_validation_errors(err, [1, "then", 0]))

    assert records == [ValidationErrorInfo(err, (1, "then", 0))]
    assert records[0].message == "Unknown device 'abc'"
    assert str(records[0]) == "Unknown device 'abc' at '[1].then[0]'"
    assert err.__traceback__ is None
    assert str(next(iter_validation_errors(err))) == "Unknown device 'abc'"


def test_iter_validation_errors_validation_errors() -> None:
    """Test the errors of a ValidationErrors get new records below the path."""
    invalid = probatio.Invalid("first", ["entity_id"])
    error = HomeAssistantError("second")
    inner = ValidationErrors(
        [
            ValidationErrorInfo(invalid, (0, "entity_id")),
            ValidationErrorInfo(error, (2,)),
        ]
    )

    outer = ValidationErrors(list(iter_validation_errors(inner, ["then"])))

    assert list(iter_validation_errors(outer, [1])) == [
        ValidationErrorInfo(invalid, (1, "then", 0, "entity_id")),
        ValidationErrorInfo(error, (1, "then", 2)),
    ]
    # Nothing is changed
    assert inner.errors == (
        ValidationErrorInfo(invalid, (0, "entity_id")),
        ValidationErrorInfo(error, (2,)),
    )
    assert invalid.path == ["entity_id"]


def test_validation_errors() -> None:
    """Test ValidationErrors holds its errors and reads as the first one."""
    invalid = probatio.Invalid("first", ["entity_id"])
    error = HomeAssistantError("second")

    err = ValidationErrors(
        [ValidationErrorInfo(invalid, (0, "entity_id")), ValidationErrorInfo(error, ())]
    )

    assert isinstance(err, HomeAssistantError)
    assert not isinstance(err, probatio.Invalid)
    assert err.errors == (
        ValidationErrorInfo(invalid, (0, "entity_id")),
        ValidationErrorInfo(error, ()),
    )
    assert str(err) == "first at '[0].entity_id'"
    assert str(ValidationErrors(err.errors[1:])) == "second"


def test_validation_errors_requires_an_error() -> None:
    """Test a ValidationErrors without errors can't be created."""
    with pytest.raises(ValueError, match="requires at least one error"):
        raise ValidationErrors([])


@pytest.mark.usefixtures("hass")
def test_validation_errors_text_is_lazy() -> None:
    """Test the message of a translated error is not looked up when collecting."""
    error = HomeAssistantError(
        translation_domain="homeassistant",
        translation_key="service_not_found",
        translation_placeholders={"domain": "test", "service": "missing"},
    )
    errors: list[ValidationErrors] = []

    def collect() -> None:
        errors.append(ValidationErrors(list(iter_validation_errors(error, [1]))))

    # The lookup is not allowed in another thread
    thread = threading.Thread(target=collect)
    thread.start()
    thread.join()

    assert str(errors[0]) == "Action test.missing not found at '[1]'"
    assert validation_errors_as_dicts(errors[0]) == [
        {
            "message": "Action test.missing not found",
            "path": [1],
            "code": None,
            "translation_key": "service_not_found",
            "translation_domain": "homeassistant",
            "translation_placeholders": {"domain": "test", "service": "missing"},
        }
    ]


def test_text_uses_msg_and_message_uses_error_message() -> None:
    """Test the text is the one of probatio.Invalid, the message is for clients."""
    err = probatio.Invalid("the text", ["a"], "the message")

    record = next(iter_validation_errors(err, [0]))

    assert record.message == "the message"
    assert str(record) == "the text at '[0].a'"
    assert str(ValidationErrors([record])) == str(record)


@pytest.mark.parametrize(
    ("segment", "expected_segment", "expected_text"),
    [
        pytest.param("name", "name", "bad at 'data.name'", id="str"),
        pytest.param(3, 3, "bad at 'data[3]'", id="int"),
        pytest.param(True, "True", "bad at 'data[True]'", id="bool"),
        pytest.param(1.5, "1.5", "bad at 'data[1.5]'", id="float"),
        pytest.param(None, "None", "bad at 'data[None]'", id="none"),
        pytest.param(_Key.NAME, "name", "bad at 'data.name'", id="str_enum"),
    ],
)
def test_path_segments(
    segment: Any, expected_segment: str | int, expected_text: str
) -> None:
    """Test path segments are kept in the record and are str or int for clients."""
    err = probatio.Invalid("bad", ["data", segment])

    record = next(iter_validation_errors(err))

    assert record.path[-1] is segment
    assert str(record) == expected_text
    path = validation_errors_as_dicts(err)[0]["path"]
    assert path == ["data", expected_segment]
    assert type(path[-1]) is type(expected_segment)
    assert json_bytes(path)


def test_group_segment() -> None:
    """Test a trailing group is kept in the record and dropped for clients."""
    schema = probatio.Schema(
        {
            "repeat": {
                probatio.Exclusive("count", "repeat"): int,
                probatio.Exclusive("while", "repeat"): int,
            }
        }
    )
    with pytest.raises(probatio.Invalid) as exc_info:
        schema({"repeat": {"count": 1, "while": 1}})

    records = list(iter_validation_errors(exc_info.value, [0]))

    assert [record.path for record in records] == [(0, "repeat", "repeat")]
    assert type(records[0].path[-1]) is VirtualPathComponent
    assert str(records[0]).endswith(" at '[0].repeat.<repeat>'")
    assert validation_errors_as_dicts(ValidationErrors(records)) == [
        {
            "message": "two or more values in the same group of exclusion 'repeat'",
            "path": [0, "repeat"],
            "code": "exclusive",
            "translation_key": "exclusive_group",
            "translation_domain": None,
            "translation_placeholders": {"group": "repeat"},
        }
    ]


@pytest.mark.parametrize(
    ("validator", "value", "expected"),
    [
        pytest.param(
            probatio.Schema({probatio.Required("a"): int}),
            {},
            {
                "message": "required key not provided",
                "path": ["a"],
                "code": "required",
                "translation_key": "required",
                "translation_domain": None,
                "translation_placeholders": {},
            },
            id="required",
        ),
        pytest.param(
            probatio.Schema({"a": probatio.Range(max=timedelta(seconds=5))}),
            {"a": timedelta(seconds=9)},
            {
                "message": "value must be at most 0:00:05",
                "path": ["a"],
                "code": "range",
                "translation_key": "range_max",
                "translation_domain": None,
                "translation_placeholders": {"max": "0:00:05"},
            },
            id="timedelta_placeholder",
        ),
        pytest.param(
            probatio.Schema({"a": probatio.In([_Unserializable(), _Key.NAME])}),
            {"a": "b"},
            {
                "message": (
                    "value must be one of [<unserializable>, <_Key.NAME: 'name'>]"
                ),
                "path": ["a"],
                "code": "not_in_list",
                "translation_key": "value_one_of",
                "translation_domain": None,
                "translation_placeholders": {"values": ["<unserializable>", "name"]},
            },
            id="object_placeholder",
        ),
        pytest.param(
            probatio.Schema({probatio.Secret("password"): cv.entity_id}),
            {"password": "s3cr3t"},
            {
                "message": "invalid value",
                "path": ["password"],
                "code": None,
                "translation_key": None,
                "translation_domain": None,
                "translation_placeholders": {},
            },
            id="secret",
        ),
    ],
)
def test_validation_errors_as_dicts(
    validator: probatio.Schema, value: Any, expected: dict[str, Any]
) -> None:
    """Test a probatio error is serialized to a JSON serializable dict."""
    with pytest.raises(probatio.Invalid) as exc_info:
        validator(value)

    assert validation_errors_as_dicts(exc_info.value) == [expected]
    assert json_bytes(validation_errors_as_dicts(exc_info.value))


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        pytest.param(
            HomeAssistantError("Unknown device 'abc'"),
            {
                "message": "Unknown device 'abc'",
                "path": [0],
                "code": None,
                "translation_key": None,
                "translation_domain": None,
                "translation_placeholders": {},
            },
            id="not_translated",
        ),
        pytest.param(
            HomeAssistantError(
                "Timed out",
                translation_domain="test",
                translation_key="timeout",
                # Integrations don't always pass str values
                translation_placeholders={  # type: ignore[dict-item]
                    "timeout": timedelta(seconds=5),
                    "attempts": 3,
                    "entities": ("light.a", _Unserializable()),
                },
            ),
            {
                "message": "Timed out",
                "path": [0],
                "code": None,
                "translation_key": "timeout",
                "translation_domain": "test",
                "translation_placeholders": {
                    "timeout": "0:00:05",
                    "attempts": 3,
                    "entities": ["light.a", "<unserializable>"],
                },
            },
            id="translated",
        ),
    ],
)
def test_validation_errors_as_dicts_homeassistant_error(
    err: HomeAssistantError, expected: dict[str, Any]
) -> None:
    """Test a HomeAssistantError is serialized to a JSON serializable dict."""
    records = list(iter_validation_errors(err, [0]))

    assert validation_errors_as_dicts(ValidationErrors(records)) == [expected]
    assert json_bytes(validation_errors_as_dicts(ValidationErrors(records)))


def test_no_reference_cycles() -> None:
    """Test a record does not keep the frames which raised its error alive."""

    def validate() -> None:
        raise HomeAssistantError("bad")

    def collect() -> None:
        errors: list[ValidationErrorInfo] = []
        for index in range(3):
            try:
                validate()
            except HomeAssistantError as err:
                errors.extend(iter_validation_errors(err, [index]))
        raise ValidationErrors(errors)

    gc.collect()
    gc.disable()
    try:
        for _ in range(200):
            with pytest.raises(ValidationErrors):
                collect()
        unreachable = gc.collect()
    finally:
        gc.enable()

    assert unreachable == 0
