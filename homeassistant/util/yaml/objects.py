"""Custom yaml object types."""
from __future__ import annotations

from dataclasses import dataclass

import yaml


class NodeListClass(list):
    """Wrapper class to be able to add attributes on a list."""


class NodeDictClass(dict):
    """Wrapper class to be able to add attributes on a dict."""


def wrap_for_setattr(obj):  # type: ignore[no-untyped-def]
    """Wrap an arbitrary object to be able to add attributes to it."""
    if isinstance(obj, list):
        return NodeListClass(obj)

    typ = type(obj)

    # Create a subclass of `typ` to be able to add attributes
    cls = type(f"DynamicNode{typ.__name__.capitalize()}Class", (typ,), {})

    # Return an instance of `cls` with value `obj`
    return cls(obj)


@dataclass(slots=True, frozen=True)
class Input:
    """Input that should be substituted."""

    name: str

    @classmethod
    def from_node(cls, loader: yaml.Loader, node: yaml.nodes.Node) -> Input:
        """Create a new placeholder from a node."""
        return cls(node.value)
