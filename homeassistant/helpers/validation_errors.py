"""Helpers to collect, locate and serialize config validation errors.

Validators raise the first error they find. To report all errors of a config
at once, for example to show each error next to the field it is about in an
editor, the code which validates the parts of a config can catch the error of
each part, turn it into records with iter_validation_errors, and raise all
records together as a ValidationErrors. validation_errors_as_dicts gives the
errors in the form which is returned to API clients.
"""

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypedDict, override

import probatio
from probatio import VirtualPathComponent
from probatio.error import render_path

from homeassistant.exceptions import HomeAssistantError

_SECRET_MESSAGE = "invalid value"


@dataclass(slots=True, frozen=True, repr=False)
class ValidationErrorInfo:
    """A single validation error and the path of the config it is about.

    A record holds one error, and its path is the whole path: the path of the
    exception is not used. An exception which holds several errors, which is
    a ValidationErrors or a MultipleInvalid with errors, can't be put in a
    record: iter_validation_errors gives a record for each of its errors.

    The segments of the path are kept as they are in the config, so the path
    can be used to look up the value. They are not always str or int.

    The message of a translated HomeAssistantError can only be looked up in
    the event loop, so message and __str__ must be used there when the record
    may hold one.
    """

    exception: probatio.Invalid | HomeAssistantError
    path: tuple[Any, ...]

    def __post_init__(self) -> None:
        """Validate the exception and make the path a tuple."""
        if isinstance(self.exception, ValidationErrors) or (
            isinstance(self.exception, probatio.MultipleInvalid)
            and self.exception.errors
        ):
            raise ValueError(
                f"A record can't hold a {type(self.exception).__name__} with "
                "errors, use iter_validation_errors to get a record for each"
            )
        object.__setattr__(self, "path", tuple(self.path))

    @property
    def message(self) -> str:
        """Return the error message, without the path.

        The message of a secret error may echo the value, it is replaced.
        """
        err = self.exception
        if not isinstance(err, probatio.Invalid):
            return str(err)
        if err.secret:
            return _SECRET_MESSAGE
        if isinstance(err, probatio.MultipleInvalid) and not err.errors:
            # It has no msg
            return str(err)
        return err.msg

    @override
    def __repr__(self) -> str:
        """Return the representation, without the message of a secret error."""
        err = self.exception
        if isinstance(err, probatio.Invalid) and err.secret:
            exception = f"<secret {type(err).__name__}>"
        else:
            exception = repr(err)
        return f"{type(self).__name__}(exception={exception}, path={self.path!r})"

    @override
    def __str__(self) -> str:
        """Return the error message with the path, like probatio.Invalid."""
        if not self.path:
            return self.message
        return f"{self.message} at '{render_path(list(self.path))}'"


class ValidationErrors(HomeAssistantError):
    """All validation errors of a config, raised when collecting errors."""

    def __init__(self, errors: Iterable[ValidationErrorInfo]) -> None:
        """Initialize."""
        self.errors = tuple(errors)
        if not self.errors:
            raise ValueError("ValidationErrors requires at least one error")
        # Passed on so the exception can be copied and represented
        super().__init__(self.errors)

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
    """Clear the traceback of err and of the exceptions it holds or is chained to."""
    seen: set[int] = set()
    pending: list[BaseException | None] = [err]
    while pending:
        exc = pending.pop()
        if exc is None or id(exc) in seen:
            continue
        seen.add(id(exc))
        exc.__traceback__ = None
        pending += (exc.__cause__, exc.__context__)
        if isinstance(exc, probatio.MultipleInvalid):
            pending += exc.errors
        elif isinstance(exc, ValidationErrors):
            pending += (info.exception for info in exc.errors)
        elif isinstance(exc, BaseExceptionGroup):
            pending += exc.exceptions


def _iter_located(
    err: probatio.Invalid | HomeAssistantError, path: tuple[Any, ...]
) -> Iterator[ValidationErrorInfo]:
    """Yield a record for each error in err, located below path."""
    if isinstance(err, ValidationErrors):
        for info in err.errors:
            yield ValidationErrorInfo(info.exception, (*path, *info.path))
    elif isinstance(err, probatio.MultipleInvalid) and err.errors:
        for sub_err in err.errors:
            yield from _iter_located(sub_err, path)
    elif isinstance(err, probatio.Invalid):
        # Also a MultipleInvalid without errors: something was rejected
        yield ValidationErrorInfo(err, (*path, *err.path))
    else:
        yield ValidationErrorInfo(err, path)


def iter_validation_errors(
    err: probatio.Invalid | HomeAssistantError, path: Sequence[Any] = ()
) -> Iterator[ValidationErrorInfo]:
    """Return the errors in err as records, located below path.

    There is one record for each single error, and at least one: a
    MultipleInvalid and a ValidationErrors are flattened, also when nested.

    The traceback of err, and of every exception it holds or is chained to,
    is cleared when this is called, to not keep the frames which raised them
    alive.
    """
    _clear_tracebacks(err)
    return _iter_located(err, tuple(path))


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
    return [_json_segment(segment) for segment in path]


def _json_int(value: int) -> int | str:
    """Return an int as a JSON value, the encoder only takes 64 bits."""
    value = int(value)
    return value if -(2**63) <= value < 2**64 else str(value)


def _json_segment(segment: Any) -> str | int:
    """Return a path segment as a str or an int."""
    if isinstance(segment, Enum):
        segment = segment.value
    if isinstance(segment, int) and not isinstance(segment, bool):
        return _json_int(segment)
    return str(segment)


def _json_value(value: Any) -> Any:
    """Return a placeholder value as a JSON value."""
    if isinstance(value, Enum):
        value = value.value
    if value is None or isinstance(value, (bool, float, str)):
        return value
    if isinstance(value, int):
        return _json_int(value)
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
