"""Custom yaml object types."""
from __future__ import annotations

from dataclasses import dataclass

import yaml


class NodeListClass(list):
    """Wrapper class to be able to add attributes on a list."""


class NodeStrClass(str):
    """Wrapper class to be able to add attributes on a string."""


@dataclass(frozen=True)
class Input:
    """Input that should be substituted."""

    name: str

    @classmethod
    def from_node(cls, loader: yaml.Loader, node: yaml.nodes.Node) -> Input:
        """Create a new placeholder from a node."""
        return cls(node.value)
