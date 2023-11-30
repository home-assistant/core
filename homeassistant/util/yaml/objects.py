"""Custom yaml object types."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import voluptuous as vol
from voluptuous.schema_builder import _compile_scalar
import yaml


class NodeListClass(list):
    """Wrapper class to be able to add attributes on a list."""


class NodeStrClass(str):
    """Wrapper class to be able to add attributes on a string."""

    def __voluptuous_compile__(self, schema: vol.Schema) -> Any:
        """Needed because vol.Schema.compile does not handle str subclasses."""
        return _compile_scalar(self)


class NodeDictClass(dict):
    """Wrapper class to be able to add attributes on a dict."""


@dataclass(slots=True, frozen=True)
class Input:
    """Input that should be substituted."""

    name: str

    @classmethod
    def from_node(cls, loader: yaml.Loader, node: yaml.nodes.Node) -> Input:
        """Create a new placeholder from a node."""
        return cls(node.value)
