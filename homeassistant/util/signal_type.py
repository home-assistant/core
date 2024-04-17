"""Define SignalTypes for dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVarTuple

_Ts = TypeVarTuple("_Ts")


@dataclass(frozen=True)
class _SignalTypeBase(Generic[*_Ts]):
    """Generic base class for SignalType."""

    name: str

    def __hash__(self) -> int:
        """Return hash of name."""

        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        """Check equality for dict keys to be compatible with str."""

        if isinstance(other, str):
            return self.name == other
        if isinstance(other, SignalType):
            return self.name == other.name
        return False


@dataclass(frozen=True, eq=False)
class SignalType(_SignalTypeBase[*_Ts]):
    """Generic string class for signal to improve typing."""


@dataclass(frozen=True, eq=False)
class SignalTypeFormat(_SignalTypeBase[*_Ts]):
    """Generic string class for signal. Requires call to 'format' before use."""

    def format(self, *args: Any, **kwargs: Any) -> SignalType[*_Ts]:
        """Format name and return new SignalType instance."""
        return SignalType(self.name.format(*args, **kwargs))
