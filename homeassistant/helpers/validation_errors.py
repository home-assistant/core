"""Helpers to collect, locate and serialize config validation errors.

Validators raise the first error they find. To report all errors of a config
at once, for example to show each error next to the field it is about in an
editor, the code which validates the parts of a config can catch the error of
each part, turn it into records with iter_validation_errors, and raise all
records together as a ValidationErrors. validation_errors_as_dicts gives the
errors in the form which is returned to API clients.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypedDict, override

import probatio
from probatio import VirtualPathComponent
from probatio.error import render_path

from homeassistant.exceptions import HomeAssistantError

_SECRET_MESSAGE = "invalid value"


@dataclass(slots=True, frozen=True)
class ValidationErrorInfo:
    """A validation error and the path of the config it is about.

    The segments of the path are kept as they are in the config, so the path
    can be used to look up the value. They are not always str or int.

    The message of a translated HomeAssistantError can only be looked up in
    the event loop, so message and __str__ must be used there when the record
    may hold one.
    """

    exception: probatio.Invalid | HomeAssistantError
    path: tuple[Any, ...]

    @property
    def message(self) -> str:
        """Return the error message, without the path.

        The message of a secret error may echo the value, it is replaced.
        """
        if isinstance(self.exception, probatio.Invalid) and not isinstance(
            self.exception, probatio.MultipleInvalid
        ):
            if self.exception.secret:
                return _SECRET_MESSAGE
            return self.exception.error_message
        # A HomeAssistantError, or a MultipleInvalid without errors
        return str(self.exception)

    @override
    def __str__(self) -> str:
        """Return the error message with the path, like probatio.Invalid."""
        if (
            isinstance(self.exception, probatio.Invalid)
            and not isinstance(self.exception, probatio.MultipleInvalid)
            and not self.exception.secret
        ):
            message = self.exception.msg
        else:
            message = self.message
        if not self.path:
            return message
        return f"{message} at '{render_path(list(self.path))}'"


class ValidationErrors(HomeAssistantError):
    """All validation errors of a config, raised when collecting errors."""

    def __init__(self, errors: Sequence[ValidationErrorInfo]) -> None:
        """Initialize."""
        if not errors:
            raise ValueError("ValidationErrors requires at least one error")
        super().__init__()
        self.errors = tuple(errors)

    @override
    def __str__(self) -> str:
        """Return the first error, with its path.

        Must be called in the event loop when the first error may be a
        translated HomeAssistantError.
        """
        # Not rendered in __init__: the message of a translated error can
        # only be looked up in the event loop
        return str(self.errors[0])


def _clear_tracebacks(err: BaseException) -> None:
    """Clear the traceback of err and of the exceptions it is chained to."""
    seen: set[int] = set()
    pending: list[BaseException | None] = [err]
    while pending:
        exc = pending.pop()
        if exc is None or id(exc) in seen:
            continue
        seen.add(id(exc))
        exc.__traceback__ = None
        pending += (exc.__cause__, exc.__context__)


def iter_validation_errors(
    err: probatio.Invalid | HomeAssistantError, path: Sequence[Any] = ()
) -> Iterator[ValidationErrorInfo]:
    """Yield the errors in err, located below path.

    At least one error is yielded. The traceback of an error, and of the
    exceptions it is chained to, is cleared when it is put in a record, to not
    keep the frames which raised them alive.
    """
    if isinstance(err, ValidationErrors):
        for info in err.errors:
            yield ValidationErrorInfo(info.exception, (*path, *info.path))
    elif isinstance(err, probatio.MultipleInvalid) and err.errors:
        for sub_err in err.errors:
            yield from iter_validation_errors(sub_err, path)
    elif isinstance(err, probatio.MultipleInvalid):
        # Without errors it is still an error: something was rejected
        _clear_tracebacks(err)
        yield ValidationErrorInfo(err, tuple(path))
    elif isinstance(err, probatio.Invalid):
        _clear_tracebacks(err)
        yield ValidationErrorInfo(err, (*path, *err.path))
    else:
        _clear_tracebacks(err)
        yield ValidationErrorInfo(err, tuple(path))


class ValidationErrorDict(TypedDict):
    """A validation error, as returned to API clients."""

    message: str
    path: list[str | int]
    code: str | None
    translation_key: str | None
    translation_domain: str | None
    translation_placeholders: dict[str, Any]


def _json_path(path: tuple[Any, ...]) -> list[str | int]:
    """Return a path as a list of str and int, without a trailing group."""
    if path and isinstance(path[-1], VirtualPathComponent):
        # A group is not a key of the config, the error is about its parent
        path = path[:-1]
    return [
        int(segment)
        if isinstance(segment, int) and not isinstance(segment, bool)
        else str(segment)
        for segment in path
    ]


def _json_value(value: Any) -> Any:
    """Return a placeholder value as a JSON value."""
    if isinstance(value, Enum):
        value = value.value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return str(value)


def _json_placeholders(placeholders: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return translation placeholders with JSON values."""
    if not placeholders:
        return {}
    return {str(key): _json_value(value) for key, value in placeholders.items()}


def validation_error_as_dict(info: ValidationErrorInfo) -> ValidationErrorDict:
    """Return a validation error as a JSON serializable dict.

    Must be called in the event loop when the record may hold a translated
    HomeAssistantError.
    """
    err = info.exception
    path = _json_path(info.path)
    if not isinstance(err, probatio.Invalid):
        return {
            "message": info.message,
            "path": path,
            "code": None,
            "translation_key": err.translation_key,
            "translation_domain": err.translation_domain,
            "translation_placeholders": _json_placeholders(
                err.translation_placeholders
            ),
        }
    if err.secret:
        # The message and the placeholders may echo the value
        return {
            "message": info.message,
            "path": path,
            "code": err.code,
            "translation_key": None,
            "translation_domain": None,
            "translation_placeholders": {},
        }
    return {
        "message": info.message,
        "path": path,
        "code": err.code,
        "translation_key": err.translation_key,
        "translation_domain": None,
        "translation_placeholders": _json_placeholders(err.placeholders),
    }


def validation_errors_as_dicts(
    err: probatio.Invalid | HomeAssistantError,
) -> list[ValidationErrorDict]:
    """Return the errors in err as JSON serializable dicts.

    Must be called in the event loop when err may hold a translated
    HomeAssistantError.
    """
    return [validation_error_as_dict(info) for info in iter_validation_errors(err)]
