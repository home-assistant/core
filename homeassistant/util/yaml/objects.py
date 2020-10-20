"""Custom yaml object types."""
from collections import namedtuple

import yaml


class NodeListClass(list):
    """Wrapper class to be able to add attributes on a list."""


class NodeStrClass(str):
    """Wrapper class to be able to add attributes on a string."""


class Placeholder(namedtuple("Placeholder", "name")):
    """A placeholder that should be substituted."""

    @classmethod
    def from_node(cls, loader: yaml.Loader, node: yaml.nodes.Node) -> "Placeholder":
        """Create a new placeholder from a node."""
        return cls(node.value)
