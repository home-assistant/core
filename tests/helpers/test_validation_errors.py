"""Test the helpers to collect, locate and serialize config validation errors."""

from collections.abc import Callable, Iterable
import copy
from datetime import timedelta
from enum import Enum, StrEnum
import gc
import threading
from typing import Any

import probatio
from probatio import VirtualPathComponent
import pytest

from homeassistant.exceptions import (
    ConfigValidationError,
    HomeAssistantError,
    ServiceValidationError,
)
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


class _LegacyKey(str, Enum):  # noqa: UP042
    """A key of a config, which is not a StrEnum."""

    NAME = "name"


class _Mode(Enum):
    """A placeholder value which is not a str."""

    FAST = 2


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


_SECRET = "hunter2"
_SECRET_SCHEMA = probatio.Schema(
    {probatio.Secret("password"): cv.matches_regex("^a+$")}
)


def _invalid(message: str, path: list[Any] | None = None) -> probatio.Invalid:
    """Return a raised probatio.Invalid."""
    return _raised(probatio.Invalid(message, path))


def _secret_multiple_invalid() -> probatio.MultipleInvalid:
    """Return the raised error of a schema with a secret key."""
    with pytest.raises(probatio.MultipleInvalid) as exc_info:
        _SECRET_SCHEMA({"password": _SECRET})
    assert _SECRET in str(exc_info.value)
    return exc_info.value


def _secret_invalid() -> probatio.Invalid:
    """Return a raised secret error."""
    return _secret_multiple_invalid().errors[0]


def _multiple_invalid(*errors: probatio.Invalid) -> probatio.MultipleInvalid:
    """Return a raised MultipleInvalid."""
    return _raised(probatio.MultipleInvalid(list(errors)))


def _validation_errors(
    *errors: tuple[probatio.Invalid | HomeAssistantError, tuple[Any, ...]],
) -> ValidationErrors:
    """Return a raised ValidationErrors with records made by hand."""
    return _raised(
        ValidationErrors([ValidationErrorInfo(err, path) for err, path in errors])
    )


def _translated_error() -> HomeAssistantError:
    """Return a raised translated HomeAssistantError."""
    return _raised(
        HomeAssistantError(
            translation_domain="homeassistant",
            translation_key="service_not_found",
            translation_placeholders={"domain": "test", "service": "missing"},
        )
    )


def _exception_group() -> ConfigValidationError:
    """Return a raised HomeAssistantError which is an ExceptionGroup."""
    return _raised(
        ConfigValidationError(
            "service_not_found",
            [_raised(ValueError("member"))],
            translation_domain="homeassistant",
            translation_placeholders={"domain": "test", "service": "missing"},
        )
    )


def _chained(
    cause: BaseException | None = None,
    context: BaseException | None = None,
    *,
    loop: bool = False,
) -> probatio.Invalid:
    """Return a raised probatio.Invalid which is chained to other exceptions."""
    err = _invalid("bad", ["a"])
    err.__cause__ = cause
    err.__context__ = context
    for chained in filter(None, (cause, context)):
        chained.__context__ = err if loop else None
    return err


def _held_exceptions(err: BaseException | None) -> list[BaseException]:
    """Return err and every exception it holds or is chained to."""
    found: dict[int, BaseException] = {}
    pending = [err]
    while pending:
        exc = pending.pop()
        if exc is None or id(exc) in found:
            continue
        found[id(exc)] = exc
        pending += [exc.__cause__, exc.__context__]
        pending += getattr(exc, "exceptions", ())
        pending += [
            getattr(sub_err, "exception", sub_err)
            for sub_err in getattr(exc, "errors", ())
        ]
    return list(found.values())


@pytest.mark.usefixtures("hass")
@pytest.mark.parametrize(
    ("make_error", "expected"),
    [
        pytest.param(lambda: _invalid("bad"), [("bad", ())], id="invalid"),
        pytest.param(
            lambda: _invalid("bad", ["a", 1]),
            [("bad", ("a", 1))],
            id="invalid_with_path",
        ),
        pytest.param(
            lambda: _raised(
                probatio.RangeInvalid(
                    path=["a"], translation_key="range_min", placeholders={"min": 2}
                )
            ),
            [("value must be at least 2", ("a",))],
            id="invalid_subclass_without_message",
        ),
        pytest.param(
            _secret_invalid, [("invalid value", ("password",))], id="secret_invalid"
        ),
        pytest.param(
            _multiple_invalid,
            [("no validation errors", ())],
            id="empty_multiple_invalid",
        ),
        pytest.param(
            lambda: _multiple_invalid(_invalid("bad", ["a"])),
            [("bad", ("a",))],
            id="multiple_invalid_one_error",
        ),
        pytest.param(
            lambda: _multiple_invalid(_invalid("bad", ["a"]), _invalid("other")),
            [("bad", ("a",)), ("other", ())],
            id="multiple_invalid_two_errors",
        ),
        pytest.param(
            lambda: _multiple_invalid(
                _multiple_invalid(_invalid("deep", ["x"]), _multiple_invalid()),
                _invalid("flat", ["z"]),
            ),
            [("deep", ("x",)), ("no validation errors", ()), ("flat", ("z",))],
            id="nested_multiple_invalid",
        ),
        pytest.param(
            _secret_multiple_invalid,
            [("invalid value", ("password",))],
            id="multiple_invalid_secret_first",
        ),
        pytest.param(
            lambda: _multiple_invalid(_invalid("bad", ["a"]), _secret_invalid()),
            [("bad", ("a",)), ("invalid value", ("password",))],
            id="multiple_invalid_secret_last",
        ),
        pytest.param(
            lambda: _validation_errors(
                (_invalid("bad", ["a"]), (1, "a")),
                (_raised(HomeAssistantError("other")), ()),
                (_secret_invalid(), ("b", "password")),
            ),
            [("bad", (1, "a")), ("other", ()), ("invalid value", ("b", "password"))],
            id="validation_errors",
        ),
        pytest.param(
            lambda: _raised(
                ValidationErrors(
                    list(
                        iter_validation_errors(
                            _validation_errors((_invalid("bad", ["a"]), (1, "a"))),
                            ["then"],
                        )
                    )
                )
            ),
            [("bad", ("then", 1, "a"))],
            id="nested_validation_errors",
        ),
        pytest.param(
            lambda: _raised(HomeAssistantError("Unknown device")),
            [("Unknown device", ())],
            id="homeassistant_error",
        ),
        pytest.param(
            lambda: _raised(ServiceValidationError("Not allowed")),
            [("Not allowed", ())],
            id="homeassistant_error_subclass",
        ),
        pytest.param(
            _translated_error,
            [("Action test.missing not found", ())],
            id="translated_homeassistant_error",
        ),
        pytest.param(
            _exception_group,
            [("Action test.missing not found", ())],
            id="homeassistant_error_exception_group",
        ),
        pytest.param(
            lambda: _chained(cause=_raised(ValueError("cause"))),
            [("bad", ("a",))],
            id="chained_cause",
        ),
        pytest.param(
            lambda: _chained(context=_raised(ValueError("context"))),
            [("bad", ("a",))],
            id="chained_context",
        ),
        pytest.param(
            lambda: _chained(
                _raised(ValueError("cause")), _raised(TypeError("context")), loop=True
            ),
            [("bad", ("a",))],
            id="chained_in_a_loop",
        ),
        pytest.param(
            lambda: _chained(cause=_multiple_invalid(_invalid("inner", ["x"]))),
            [("bad", ("a",))],
            id="chained_to_multiple_invalid",
        ),
        pytest.param(
            lambda: _chained(
                context=_validation_errors((_invalid("inner", ["x"]), ("x",)))
            ),
            [("bad", ("a",))],
            id="chained_to_validation_errors",
        ),
    ],
)
def test_records_of_error(
    make_error: Callable[[], probatio.Invalid | HomeAssistantError],
    expected: list[tuple[str, tuple[Any, ...]]],
) -> None:
    """Test what holds for the records of any error.

    Each case is an error and the message and path of each single error in it.
    """
    err = make_error()
    paths = [(0, "k", *path) for _, path in expected]
    messages = [message for message, _ in expected]
    # The text of a probatio.Invalid with the same message and path
    texts = [
        str(probatio.Invalid(message, list(path)))
        for message, path in zip(messages, paths, strict=True)
    ]

    records = list(iter_validation_errors(err, [0, "k"]))
    carrier = ValidationErrors(records)
    dicts = validation_errors_as_dicts(carrier)

    assert [(record.message, record.path) for record in records] == list(
        zip(messages, paths, strict=True)
    )
    assert [str(record) for record in records] == texts
    # The records hold the errors themselves, and making them changes no error
    held = _held_exceptions(err)
    assert all(any(record.exception is exc for exc in held) for record in records)
    assert list(iter_validation_errors(err, [0, "k"])) == records
    assert str(carrier) == texts[0]
    assert [(item["message"], item["path"]) for item in dicts] == [
        (message, list(path)) for message, path in zip(messages, paths, strict=True)
    ]
    # A record holds a single error, so it can be made again from its fields
    assert [
        ValidationErrorInfo(record.exception, record.path) for record in records
    ] == records
    # Locating the records again adds to the path and changes nothing else
    assert list(iter_validation_errors(carrier, ["x"])) == [
        ValidationErrorInfo(record.exception, ("x", *record.path)) for record in records
    ]
    assert carrier.errors == tuple(records)
    assert [
        type(exc).__name__
        for exc in _held_exceptions(err) + _held_exceptions(carrier)
        if exc.__traceback__ is not None
    ] == []
    assert _SECRET not in (
        f"{records!r} {carrier!r} {carrier} {json_bytes(dicts).decode()}"
    )


@pytest.mark.parametrize(
    "make_error",
    [
        pytest.param(
            lambda: _multiple_invalid(_invalid("bad", ["a"])), id="multiple_invalid"
        ),
        pytest.param(
            lambda: _multiple_invalid(_multiple_invalid(_invalid("bad"))),
            id="nested_multiple_invalid",
        ),
        pytest.param(_secret_multiple_invalid, id="secret_multiple_invalid"),
        pytest.param(
            lambda: _validation_errors((_invalid("bad", ["a"]), ("a",))),
            id="validation_errors",
        ),
    ],
)
def test_record_of_several_errors(
    make_error: Callable[[], probatio.Invalid | HomeAssistantError],
) -> None:
    """Test a record can't be made from an exception which holds errors."""
    with pytest.raises(ValueError, match="use iter_validation_errors"):
        ValidationErrorInfo(make_error(), (0, "a"))


def test_record_repr() -> None:
    """Test the representation of a record does not have a secret value."""
    assert (
        repr(ValidationErrorInfo(probatio.Invalid("bad"), ("a", 0)))
        == "ValidationErrorInfo(exception=Invalid('bad'), path=('a', 0))"
    )
    assert (
        repr(ValidationErrorInfo(_secret_invalid(), ("password",)))
        == "ValidationErrorInfo(exception=<secret Invalid>, path=('password',))"
    )


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


@pytest.mark.parametrize(
    "errors",
    [
        pytest.param([], id="list"),
        pytest.param(iter(()), id="iterator"),
    ],
)
def test_validation_errors_requires_an_error(
    errors: Iterable[ValidationErrorInfo],
) -> None:
    """Test a ValidationErrors without errors can't be created."""
    with pytest.raises(ValueError, match="requires at least one error"):
        raise ValidationErrors(errors)


def test_validation_errors_from_iterator() -> None:
    """Test a ValidationErrors can be created from an iterator."""
    err = probatio.Invalid("bad", ["a"])

    carrier = ValidationErrors(iter_validation_errors(err, [0]))

    assert carrier.errors == (ValidationErrorInfo(err, (0, "a")),)


def test_validation_errors_copy_and_repr() -> None:
    """Test a ValidationErrors can be copied and represented."""
    record = ValidationErrorInfo(HomeAssistantError("bad"), ("a",))
    carrier = ValidationErrors([record, ValidationErrorInfo(_secret_invalid(), ())])

    assert copy.copy(carrier).errors == carrier.errors
    assert str(copy.deepcopy(carrier)) == "bad at 'a'"
    assert repr(carrier) == (
        "ValidationErrors((ValidationErrorInfo(exception=HomeAssistantError('bad'), "
        "path=('a',)), ValidationErrorInfo(exception=<secret Invalid>, path=())))"
    )


def test_iter_validation_errors_is_not_lazy() -> None:
    """Test the tracebacks are cleared and the path is read when called."""
    first = _invalid("first")
    second = _invalid("second")
    path = [0]

    records = iter_validation_errors(_multiple_invalid(first, second), path)
    path[0] = 1

    assert first.__traceback__ is None
    assert second.__traceback__ is None
    assert [record.path for record in records] == [(0,), (0,)]


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


def test_message_and_text_use_msg() -> None:
    """Test the message and the text are the msg of a probatio.Invalid."""
    err = probatio.Invalid("the text", ["a"], "another text")

    record = next(iter_validation_errors(err, [0]))

    assert record.message == "the text"
    assert str(record) == "the text at '[0].a'"
    assert str(ValidationErrors([record])) == str(record)
    assert validation_errors_as_dicts(err)[0]["message"] == "the text"


@pytest.mark.parametrize(
    ("segment", "expected_segment", "expected_text"),
    [
        pytest.param("name", "name", "bad at 'data.name'", id="str"),
        pytest.param(3, 3, "bad at 'data[3]'", id="int"),
        pytest.param(True, "True", "bad at 'data[True]'", id="bool"),
        pytest.param(1.5, "1.5", "bad at 'data[1.5]'", id="float"),
        pytest.param(None, "None", "bad at 'data[None]'", id="none"),
        pytest.param(_Key.NAME, "name", "bad at 'data.name'", id="str_enum"),
        pytest.param(
            _LegacyKey.NAME,
            "name",
            "bad at 'data[<_LegacyKey.NAME: 'name'>]'",
            id="str_and_enum",
        ),
        pytest.param(
            _Mode.FAST, 2, "bad at 'data[<_Mode.FAST: 2>]'", id="enum_with_int_value"
        ),
        pytest.param(2**64 - 1, 2**64 - 1, f"bad at 'data[{2**64 - 1}]'", id="64_bits"),
        pytest.param(
            2**64,
            "18446744073709551616",
            "bad at 'data[18446744073709551616]'",
            id="more_than_64_bits",
        ),
        pytest.param(
            -(2**63) - 1,
            "-9223372036854775809",
            "bad at 'data[-9223372036854775809]'",
            id="less_than_64_bits",
        ),
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


def test_secret_error_text() -> None:
    """Test the text of a secret error does not have the value."""
    schema = probatio.Schema(
        {"outer": {probatio.Secret("password"): cv.matches_regex("^a+$")}}
    )
    with pytest.raises(probatio.Invalid) as exc_info:
        schema({"outer": {"password": "hunter2"}})
    assert "hunter2" in str(exc_info.value)

    records = list(iter_validation_errors(exc_info.value, [0]))

    assert len(records) == 1
    assert records[0].message == "invalid value"
    assert str(records[0]) == "invalid value at '[0].outer.password'"
    assert str(ValidationErrors(records)) == "invalid value at '[0].outer.password'"


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


def test_group_segment_not_last() -> None:
    """Test a group which is not the last segment is kept for clients."""
    err = probatio.Invalid("bad", ["a", VirtualPathComponent("group"), "b"])

    assert validation_errors_as_dicts(err)[0]["path"] == ["a", "<group>", "b"]


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
            probatio.Schema({probatio.Secret("password"): probatio.In(["allowed"])}),
            {"password": "s3cr3t"},
            {
                "message": "invalid value",
                "path": ["password"],
                "code": "not_in_list",
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
                    "large": 2**64,
                    "largest": [2**64 - 1, -(2**63)],
                    "entities": ("light.a", _Unserializable()),
                    "mode": _Mode.FAST,
                    "modes": {_Mode.FAST},
                    "frozen": frozenset({"a"}),
                    5: "not a str key",
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
                    "large": "18446744073709551616",
                    "largest": [2**64 - 1, -(2**63)],
                    "entities": ["light.a", "<unserializable>"],
                    "mode": 2,
                    "modes": [2],
                    "frozen": ["a"],
                    "5": "not a str key",
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


def _raise_plain() -> None:
    """Raise an error."""
    raise HomeAssistantError("bad")


def _raise_from() -> None:
    """Raise an error from another error."""
    try:
        int("x")
    except ValueError as err:
        raise probatio.Invalid("bad") from err


def _raise_in_except() -> None:
    """Raise an error while another error is handled."""
    try:
        int("x")
    except ValueError:
        raise HomeAssistantError("bad")


def _raise_multiple_invalid() -> None:
    """Raise a MultipleInvalid which the raising frame keeps a reference to."""
    err = probatio.MultipleInvalid([probatio.Invalid("bad")])
    raise err


def _raise_validation_errors() -> None:
    """Raise a ValidationErrors which the raising frame keeps a reference to."""
    err = ValidationErrors([ValidationErrorInfo(probatio.Invalid("bad"), ())])
    raise err


def _raise_validation_errors_of_raised_error() -> None:
    """Raise a ValidationErrors with a record made from a raised error."""
    errors: list[ValidationErrorInfo] = []
    try:
        _raise_from()
    except probatio.Invalid as err:
        errors.append(ValidationErrorInfo(err, ()))
    raise ValidationErrors(errors)


def _raise_multiple_invalid_of_raised_error() -> None:
    """Raise a MultipleInvalid with an error which was raised."""
    errors: list[probatio.Invalid] = []
    try:
        _raise_from()
    except probatio.Invalid as err:
        errors.append(err)
    raise probatio.MultipleInvalid(errors)


def _raise_from_multiple_invalid() -> None:
    """Raise an error from a MultipleInvalid with an error which was raised."""
    try:
        _raise_multiple_invalid_of_raised_error()
    except probatio.MultipleInvalid as err:
        raise HomeAssistantError("bad") from err


def _raise_from_validation_errors() -> None:
    """Raise an error from a ValidationErrors with a record of a raised error."""
    try:
        _raise_validation_errors_of_raised_error()
    except ValidationErrors as err:
        raise HomeAssistantError("bad") from err


def _raise_exception_group() -> None:
    """Raise an ExceptionGroup with an error which was raised."""
    errors: list[Exception] = []
    try:
        int("x")
    except ValueError as err:
        errors.append(err)
    raise ConfigValidationError("bad", errors)


@pytest.mark.parametrize(
    "validate",
    [
        pytest.param(_raise_plain, id="plain"),
        pytest.param(_raise_from, id="explicit_cause"),
        pytest.param(_raise_in_except, id="implicit_context"),
        pytest.param(_raise_multiple_invalid, id="multiple_invalid"),
        pytest.param(_raise_validation_errors, id="validation_errors"),
        pytest.param(
            _raise_validation_errors_of_raised_error,
            id="validation_errors_of_raised_error",
        ),
        pytest.param(_raise_from_multiple_invalid, id="from_multiple_invalid"),
        pytest.param(_raise_from_validation_errors, id="from_validation_errors"),
        pytest.param(_raise_exception_group, id="exception_group"),
    ],
)
def test_no_reference_cycles(validate: Callable[[], None]) -> None:
    """Test a record does not keep the frames which raised its error alive."""

    def collect() -> None:
        errors: list[ValidationErrorInfo] = []
        for index in range(3):
            try:
                validate()
            except (probatio.Invalid, HomeAssistantError) as err:
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
