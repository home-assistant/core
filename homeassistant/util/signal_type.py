"""Define SignalTypes for dispatcher."""

from __future__ import annotations

from typing import Any


class _SignalTypeBase[*_Ts](str):
    """Generic base class for SignalType."""

    __slots__ = ()


class SignalType[*_Ts](_SignalTypeBase[*_Ts]):
    """Generic string class for signal to improve typing."""

    __slots__ = ()


class SignalTypeFormat[*_Ts](_SignalTypeBase[*_Ts]):
    """Generic string class for signal. Requires call to 'format' before use."""

    __slots__ = ()

    def format(self, *args: Any, **kwargs: Any) -> SignalType[*_Ts]:
        """Format name and return new SignalType instance."""
        return SignalType(super().format(*args, **kwargs))
