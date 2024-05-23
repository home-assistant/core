"""Read only dictionary."""

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
