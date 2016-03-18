"""YAML utility functions."""
import logging
import os
from collections import OrderedDict

import yaml

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


def load_yaml(fname):
    """Load a YAML file."""
    try:
        with open(fname, encoding='utf-8') as conf_file:
            # If configuration file is empty YAML returns None
            # We convert that to an empty dict
            return yaml.safe_load(conf_file) or {}
    except yaml.YAMLError:
        error = 'Error reading YAML configuration file {}'.format(fname)
        _LOGGER.exception(error)
        raise HomeAssistantError(error)


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
    return OrderedDict(loader.construct_pairs(node))


yaml.SafeLoader.add_constructor('!include', _include_yaml)
yaml.SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                _ordered_dict)
