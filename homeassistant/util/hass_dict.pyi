"""Stub file for hass_dict. Provide overload for type checking."""
# ruff: noqa: PYI021  # Allow docstrings

from typing import Any, Generic, TypeVar, assert_type, overload

__all__ = [
    "HassDict",
    "HassEntryKey",
    "HassKey",
]

_T = TypeVar("_T")  # needs to be invariant

class _Key(Generic[_T]):
    """Base class for Hass key types. At runtime delegated to str."""

    def __init__(self, value: str, /) -> None: ...
    def __len__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...
    def __getitem__(self, index: int) -> str: ...

class HassEntryKey(_Key[_T]):
    """Key type for integrations with config entries."""

class HassKey(_Key[_T]):
    """Generic Hass key type."""

class HassDict(dict[_Key[Any] | str, Any]):
    """Custom dict type to provide better value type hints for Hass key types."""

    @overload  # type: ignore[override]
    def __getitem__[_S](self, key: HassEntryKey[_S], /) -> dict[str, _S]: ...
    @overload
    def __getitem__[_S](self, key: HassKey[_S], /) -> _S: ...
    @overload
    def __getitem__(self, key: str, /) -> Any: ...

    # ------
    @overload  # type: ignore[override]
    def __setitem__[_S](
        self, key: HassEntryKey[_S], value: dict[str, _S], /
    ) -> None: ...
    @overload
    def __setitem__[_S](self, key: HassKey[_S], value: _S, /) -> None: ...
    @overload
    def __setitem__(self, key: str, value: Any, /) -> None: ...

    # ------
    @overload  # type: ignore[override]
    def setdefault[_S](
        self, key: HassEntryKey[_S], default: dict[str, _S], /
    ) -> dict[str, _S]: ...
    @overload
    def setdefault[_S](self, key: HassKey[_S], default: _S, /) -> _S: ...
    @overload
    def setdefault(self, key: str, default: None = None, /) -> Any | None: ...
    @overload
    def setdefault(self, key: str, default: Any, /) -> Any: ...

    # ------
    @overload  # type: ignore[override]
    def get[_S](self, key: HassEntryKey[_S], /) -> dict[str, _S] | None: ...
    @overload
    def get[_S, _U](
        self, key: HassEntryKey[_S], default: _U, /
    ) -> dict[str, _S] | _U: ...
    @overload
    def get[_S](self, key: HassKey[_S], /) -> _S | None: ...
    @overload
    def get[_S, _U](self, key: HassKey[_S], default: _U, /) -> _S | _U: ...
    @overload
    def get(self, key: str, /) -> Any | None: ...
    @overload
    def get(self, key: str, default: Any, /) -> Any: ...

    # ------
    @overload  # type: ignore[override]
    def pop[_S](self, key: HassEntryKey[_S], /) -> dict[str, _S]: ...
    @overload
    def pop[_S](
        self, key: HassEntryKey[_S], default: dict[str, _S], /
    ) -> dict[str, _S]: ...
    @overload
    def pop[_S, _U](
        self, key: HassEntryKey[_S], default: _U, /
    ) -> dict[str, _S] | _U: ...
    @overload
    def pop[_S](self, key: HassKey[_S], /) -> _S: ...
    @overload
    def pop[_S](self, key: HassKey[_S], default: _S, /) -> _S: ...
    @overload
    def pop[_S, _U](self, key: HassKey[_S], default: _U, /) -> _S | _U: ...
    @overload
    def pop(self, key: str, /) -> Any: ...
    @overload
    def pop[_U](self, key: str, default: _U, /) -> Any | _U: ...

def _test_hass_dict_typing() -> None:  # noqa: PYI048
    """Test HassDict overloads work as intended.

    This is tested during the mypy run. Do not move it to 'tests'!
    """
    d = HassDict()
    entry_key = HassEntryKey[int]("entry_key")
    key = HassKey[int]("key")
    key2 = HassKey[dict[int, bool]]("key2")
    key3 = HassKey[set[str]]("key3")
    other_key = "domain"

    # __getitem__
    assert_type(d[entry_key], dict[str, int])
    assert_type(d[entry_key]["entry_id"], int)
    assert_type(d[key], int)
    assert_type(d[key2], dict[int, bool])

    # __setitem__
    d[entry_key] = {}
    d[entry_key] = 2  # type: ignore[call-overload]
    d[entry_key]["entry_id"] = 2
    d[entry_key]["entry_id"] = "Hello World"  # type: ignore[assignment]
    d[key] = 2
    d[key] = "Hello World"  # type: ignore[misc]
    d[key] = {}  # type: ignore[misc]
    d[key2] = {}
    d[key2] = 2  # type: ignore[misc]
    d[key3] = set()
    d[key3] = 2  # type: ignore[misc]
    d[other_key] = 2
    d[other_key] = "Hello World"

    # get
    assert_type(d.get(entry_key), dict[str, int] | None)
    assert_type(d.get(entry_key, True), dict[str, int] | bool)
    assert_type(d.get(key), int | None)
    assert_type(d.get(key, True), int | bool)
    assert_type(d.get(key2), dict[int, bool] | None)
    assert_type(d.get(key2, {}), dict[int, bool])
    assert_type(d.get(key3), set[str] | None)
    assert_type(d.get(key3, set()), set[str])
    assert_type(d.get(other_key), Any | None)
    assert_type(d.get(other_key, True), Any)
    assert_type(d.get(other_key, {})["id"], Any)

    # setdefault
    assert_type(d.setdefault(entry_key, {}), dict[str, int])
    assert_type(d.setdefault(entry_key, {})["entry_id"], int)
    assert_type(d.setdefault(key, 2), int)
    assert_type(d.setdefault(key2, {}), dict[int, bool])
    assert_type(d.setdefault(key2, {})[2], bool)
    assert_type(d.setdefault(key3, set()), set[str])
    assert_type(d.setdefault(other_key, 2), Any)
    assert_type(d.setdefault(other_key), Any | None)
    d.setdefault(entry_key, {})["entry_id"] = 2
    d.setdefault(entry_key, {})["entry_id"] = "Hello World"  # type: ignore[assignment]
    d.setdefault(key, 2)
    d.setdefault(key, "Error")  # type: ignore[misc]
    d.setdefault(key2, {})[2] = True
    d.setdefault(key2, {})[2] = "Error"  # type: ignore[assignment]
    d.setdefault(key3, set()).add("Hello World")
    d.setdefault(key3, set()).add(2)  # type: ignore[arg-type]
    d.setdefault(other_key, {})["id"] = 2
    d.setdefault(other_key, {})["id"] = "Hello World"
    d.setdefault(entry_key)  # type: ignore[call-overload]
    d.setdefault(key)  # type: ignore[call-overload]
    d.setdefault(key2)  # type: ignore[call-overload]

    # pop
    assert_type(d.pop(entry_key), dict[str, int])
    assert_type(d.pop(entry_key, {}), dict[str, int])
    assert_type(d.pop(entry_key, 2), dict[str, int] | int)
    assert_type(d.pop(key), int)
    assert_type(d.pop(key, 2), int)
    assert_type(d.pop(key, "Hello World"), int | str)
    assert_type(d.pop(key2), dict[int, bool])
    assert_type(d.pop(key2, {}), dict[int, bool])
    assert_type(d.pop(key2, 2), dict[int, bool] | int)
    assert_type(d.pop(key3), set[str])
    assert_type(d.pop(key3, set()), set[str])
    assert_type(d.pop(other_key), Any)
    assert_type(d.pop(other_key, True), Any | bool)
