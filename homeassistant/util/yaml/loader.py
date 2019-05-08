"""Custom loader."""
import yaml


# pylint: disable=too-many-ancestors
class SafeLineLoader(yaml.SafeLoader):
    """Loader class that keeps track of line numbers."""

    def compose_node(self, parent: yaml.nodes.Node,
                     index: int) -> yaml.nodes.Node:
        """Annotate a node with the first line it was seen."""
        last_line = self.line  # type: int
        node = super(SafeLineLoader,
                     self).compose_node(parent, index)  # type: yaml.nodes.Node
        node.__line__ = last_line + 1  # type: ignore
        return node
