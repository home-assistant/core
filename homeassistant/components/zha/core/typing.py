"""Typing helpers for ZHA component."""
from collections.abc import Callable
from typing import TypeVar

# pylint: disable=invalid-name
CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)
