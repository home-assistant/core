"""Define common OpenUV data models."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class OpenUvEntityDescriptionMixin:
    """Define a mixin for OpenUV entity descriptions."""

    value_fn: Callable[[dict[str, Any]], int | str]
