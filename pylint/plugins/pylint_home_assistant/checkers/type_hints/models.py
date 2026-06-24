"""Data types for type hint pattern matching."""

from dataclasses import dataclass
from enum import Enum

from astroid import nodes


class _Special(Enum):
    """Sentinel values."""

    UNDEFINED = 1


@dataclass
class TypeHintMatch:
    """Class for pattern matching."""

    function_name: str
    return_type: list[str | _Special | None] | str | _Special | None
    arg_types: dict[int, str] | None = None
    """arg_types is for positional arguments"""
    named_arg_types: dict[str, str] | None = None
    """named_arg_types is for named or keyword arguments"""
    kwargs_type: str | None = None
    """kwargs_type is for the special case `**kwargs`"""
    has_async_counterpart: bool = False
    """`function_name` and `async_function_name` share arguments and return type"""
    mandatory: bool = False
    """bypass ignore_missing_annotations"""

    def need_to_check_function(self, node: nodes.FunctionDef) -> bool:
        """Confirm if function should be checked."""
        return (
            self.function_name == node.name
            or (
                self.has_async_counterpart
                and node.name == f"async_{self.function_name}"
            )
            or (
                self.function_name.endswith("*")
                and node.name.startswith(self.function_name[:-1])
            )
        )


@dataclass(kw_only=True)
class ClassTypeHintMatch:
    """Class for pattern matching."""

    base_class: str
    exclude_base_classes: set[str] | None = None
    matches: list[TypeHintMatch]
