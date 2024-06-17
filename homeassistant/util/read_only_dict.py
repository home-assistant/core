"""Read only dictionary."""

from copy import deepcopy
from typing import Any


def _readonly(*args: Any, **kwargs: Any) -> Any:
    """Raise an exception when a read only dict is modified."""
    raise RuntimeError("Cannot modify ReadOnlyDict")


class ReadOnlyDict[_KT, _VT](dict[_KT, _VT]):
    """Read only version of dict that is compatible with dict types."""

    __setitem__ = _readonly
    __delitem__ = _readonly
    pop = _readonly
    popitem = _readonly
    clear = _readonly
    update = _readonly
    setdefault = _readonly

    def __copy__(self) -> dict[_KT, _VT]:
        """Create a shallow copy."""
        return ReadOnlyDict(self)

    def __deepcopy__(self, memo: Any) -> dict[_KT, _VT]:
        """Create a deep copy."""
        return ReadOnlyDict(
            {deepcopy(key, memo): deepcopy(value, memo) for key, value in self.items()}
        )
