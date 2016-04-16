"""YAML utility functions."""
import logging
import os
from collections import OrderedDict

import yaml

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-ancestors
class SafeLineLoader(yaml.SafeLoader):
    """Loader class that keeps track of line numbers."""

    def compose_node(self, parent, index):
        """Annotate a node with the first line it was seen."""
        last_line = self.line
        node = super(SafeLineLoader, self).compose_node(parent, index)
        node.__line__ = last_line + 1
        return node


def load_yaml(fname):
    """Load a YAML file."""
    try:
        with open(fname, encoding='utf-8') as conf_file:
            # If configuration file is empty YAML returns None
            # We convert that to an empty dict
            return yaml.load(conf_file, Loader=SafeLineLoader) or {}
    except yaml.YAMLError as exc:
        _LOGGER.error(exc)
        raise HomeAssistantError(exc)


def _include_yaml(loader, node):
    """Load another YAML file and embeds it using the !include tag.

    Example:
        device_tracker: !include device_tracker.yaml
    """
    fname = os.path.join(os.path.dirname(loader.name), node.value)
    return load_yaml(fname)


def _ordered_dict(loader, node):
    """Load YAML mappings into an ordered dict to preserve key order."""
    loader.flatten_mapping(node)
    nodes = loader.construct_pairs(node)

    seen = {}
    for (key, _), (node, _) in zip(nodes, node.value):
        line = getattr(node, '__line__', 'unknown')
        if key in seen:
            fname = getattr(loader.stream, 'name', '')
            first_mark = yaml.Mark(fname, 0, seen[key], -1, None, None)
            second_mark = yaml.Mark(fname, 0, line, -1, None, None)
            raise yaml.MarkedYAMLError(
                context="duplicate key: \"{}\"".format(key),
                context_mark=first_mark, problem_mark=second_mark,
            )
        seen[key] = line

    return OrderedDict(nodes)

yaml.SafeLoader.add_constructor('!include', _include_yaml)
yaml.SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                _ordered_dict)
