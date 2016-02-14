"""
YAML utility functions.
"""
from collections import OrderedDict
import logging
import os

import yaml

from homeassistant.exceptions import HomeAssistantError


_LOGGER = logging.getLogger(__name__)

def load_yaml(fname):
    """Load a YAML file."""
    try:
        return _merge_multidoc_yaml(fname)
    except yaml.YAMLError:
        error = 'Error reading YAML configuration file {}'.format(fname)
        _LOGGER.exception(error)
        raise HomeAssistantError(error)


def _merge_multidoc_yaml(fname):
    with open(fname, encoding='utf-8') as conf_file:
        config = {}
        for document in yaml.safe_load_all(conf_file):
            if not isinstance(document, dict):
                return document
            for key, value in document.items():
                if key in config:
                    oldvalue = config[key]
                    if not isinstance(oldvalue, list):
                        oldvalue = [ oldvalue ]
                        config[key] = oldvalue

                    if isinstance(value, list):
                        oldvalue.extend(value)
                    else:
                        oldvalue.append(value)
                else:
                    config[key] = value
    return config

def _include_yaml(loader, node):
    """
    Loads another YAML file and embeds it using the !include tag.

    Example:
        device_tracker: !include device_tracker.yaml
    """
    fname = os.path.join(os.path.dirname(loader.name), node.value)
    return load_yaml(fname)


def _ordered_dict(loader, node):
    """
    Loads YAML mappings into an ordered dict to preserve key order.
    """
    loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node))


yaml.SafeLoader.add_constructor('!include', _include_yaml)
yaml.SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                _ordered_dict)
