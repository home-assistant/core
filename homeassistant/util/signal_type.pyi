"""Stub file for signal_type. Provide overload for type checking."""
# ruff: noqa: PYI021  # Allow docstring

from typing import Any, assert_type

__all__ = [
    "SignalType",
    "SignalTypeFormat",
]

class _SignalTypeBase[*_Ts]:
    """Custom base class for SignalType. At runtime delegate to str.

    For type checkers pretend to be its own separate class.
    """

    def __init__(self, value: str, /) -> None: ...
    def __hash__(self) -> int: ...
    def __eq__(self, other: object, /) -> bool: ...

class SignalType[*_Ts](_SignalTypeBase[*_Ts]):
    """Generic string class for signal to improve typing."""

class SignalTypeFormat[*_Ts](_SignalTypeBase[*_Ts]):
    """Generic string class for signal. Requires call to 'format' before use."""

    def format(self, *args: Any, **kwargs: Any) -> SignalType[*_Ts]: ...

def _test_signal_type_typing() -> None:  # noqa: PYI048
    """Test SignalType and dispatcher overloads work as intended.

    This is tested during the mypy run. Do not move it to 'tests'!
    """
    # pylint: disable=import-outside-toplevel
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.dispatcher import (
        async_dispatcher_connect,
        async_dispatcher_send,
    )

    hass: HomeAssistant
    def test_func(a: int) -> None: ...
    def test_func_other(a: int, b: str) -> None: ...

    # No type validation for str signals
    signal_str = "signal"
    async_dispatcher_connect(hass, signal_str, test_func)
    async_dispatcher_connect(hass, signal_str, test_func_other)
    async_dispatcher_send(hass, signal_str, 2)
    async_dispatcher_send(hass, signal_str, 2, "Hello World")

    # Using SignalType will perform type validation on target and args
    signal_1: SignalType[int] = SignalType("signal")
    assert_type(signal_1, SignalType[int])
    async_dispatcher_connect(hass, signal_1, test_func)
    async_dispatcher_connect(hass, signal_1, test_func_other)  # type: ignore[arg-type]
    async_dispatcher_send(hass, signal_1, 2)
    async_dispatcher_send(hass, signal_1, "Hello World")  # type: ignore[misc]

    # SignalTypeFormat cannot be used for dispatcher_connect / dispatcher_send
    # Call format() on it first to convert it to a SignalType
    signal_format: SignalTypeFormat[int] = SignalTypeFormat("signal_")
    signal_2 = signal_format.format("2")
    assert_type(signal_format, SignalTypeFormat[int])
    assert_type(signal_2, SignalType[int])
    async_dispatcher_connect(hass, signal_format, test_func)  # type: ignore[call-overload]
    async_dispatcher_connect(hass, signal_2, test_func)
    async_dispatcher_send(hass, signal_format, 2)  # type: ignore[call-overload]
    async_dispatcher_send(hass, signal_2, 2)
