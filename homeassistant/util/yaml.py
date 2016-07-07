"""YAML utility functions."""
import logging
import os
from collections import OrderedDict

import glob
import yaml
try:
    import keyring
except ImportError:
    keyring = None

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
_SECRET_NAMESPACE = 'homeassistant'
_SECRET_YAML = 'secrets.yaml'


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


def _include_dir_named_yaml(loader, node):
    """Load multiple files from directory as a dictionary."""
    mapping = OrderedDict()
    files = os.path.join(os.path.dirname(loader.name), node.value, '*.yaml')
    for fname in glob.glob(files):
        filename = os.path.splitext(os.path.basename(fname))[0]
        mapping[filename] = load_yaml(fname)
    return mapping


def _include_dir_merge_named_yaml(loader, node):
    """Load multiple files from directory as a merged dictionary."""
    mapping = OrderedDict()
    files = os.path.join(os.path.dirname(loader.name), node.value, '*.yaml')
    for fname in glob.glob(files):
        if os.path.basename(fname) == _SECRET_YAML:
            continue
        loaded_yaml = load_yaml(fname)
        if isinstance(loaded_yaml, dict):
            mapping.update(loaded_yaml)
    return mapping


def _include_dir_list_yaml(loader, node):
    """Load multiple files from directory as a list."""
    files = os.path.join(os.path.dirname(loader.name), node.value, '*.yaml')
    return [load_yaml(f) for f in glob.glob(files)
            if os.path.basename(f) != _SECRET_YAML]


def _include_dir_merge_list_yaml(loader, node):
    """Load multiple files from directory as a merged list."""
    files = os.path.join(os.path.dirname(loader.name), node.value, '*.yaml')
    merged_list = []
    for fname in glob.glob(files):
        if os.path.basename(fname) == _SECRET_YAML:
            continue
        loaded_yaml = load_yaml(fname)
        if isinstance(loaded_yaml, list):
            merged_list.extend(loaded_yaml)
    return merged_list


def _ordered_dict(loader, node):
    """Load YAML mappings into an ordered dictionary to preserve key order."""
    loader.flatten_mapping(node)
    nodes = loader.construct_pairs(node)

    seen = {}
    min_line = None
    for (key, _), (node, _) in zip(nodes, node.value):
        line = getattr(node, '__line__', 'unknown')
        if line != 'unknown' and (min_line is None or line < min_line):
            min_line = line
        if key in seen:
            fname = getattr(loader.stream, 'name', '')
            first_mark = yaml.Mark(fname, 0, seen[key], -1, None, None)
            second_mark = yaml.Mark(fname, 0, line, -1, None, None)
            raise yaml.MarkedYAMLError(
                context="duplicate key: \"{}\"".format(key),
                context_mark=first_mark, problem_mark=second_mark,
            )
        seen[key] = line

    processed = OrderedDict(nodes)
    processed.__config_file__ = loader.name
    processed.__line__ = min_line
    return processed


def _env_var_yaml(loader, node):
    """Load environment variables and embed it into the configuration YAML."""
    if node.value in os.environ:
        return os.environ[node.value]
    else:
        _LOGGER.error("Environment variable %s not defined.", node.value)
        raise HomeAssistantError(node.value)


# pylint: disable=protected-access
def _secret_yaml(loader, node):
    """Load secrets and embed it into the configuration YAML."""
    # Create secret cache on loader and load secrets.yaml
    if not hasattr(loader, '_SECRET_CACHE'):
        loader._SECRET_CACHE = {}

    secret_path = os.path.join(os.path.dirname(loader.name), _SECRET_YAML)
    if secret_path not in loader._SECRET_CACHE:
        if os.path.isfile(secret_path):
            loader._SECRET_CACHE[secret_path] = load_yaml(secret_path)
            secrets = loader._SECRET_CACHE[secret_path]
            if 'logger' in secrets:
                logger = str(secrets['logger']).lower()
                if logger == 'debug':
                    _LOGGER.setLevel(logging.DEBUG)
                else:
                    _LOGGER.error("secrets.yaml: 'logger: debug' expected,"
                                  " but 'logger: %s' found", logger)
                del secrets['logger']
        else:
            loader._SECRET_CACHE[secret_path] = None
    secrets = loader._SECRET_CACHE[secret_path]

    # Retrieve secret, first from secrets.yaml, then from keyring
    if secrets is not None and node.value in secrets:
        _LOGGER.debug('Secret %s retrieved from secrets.yaml.', node.value)
        return secrets[node.value]
    for sname, sdict in loader._SECRET_CACHE.items():
        if node.value in sdict:
            _LOGGER.debug('Secret %s retrieved from secrets.yaml in other '
                          'folder %s', node.value, sname)
            return sdict[node.value]

    if keyring:
        # do ome keyring stuff
        pwd = keyring.get_password(_SECRET_NAMESPACE, node.value)
        if pwd:
            _LOGGER.debug('Secret %s retrieved from keyring.', node.value)
            return pwd

    _LOGGER.error('Secret %s not defined.', node.value)
    raise HomeAssistantError(node.value)

yaml.SafeLoader.add_constructor('!include', _include_yaml)
yaml.SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                _ordered_dict)
yaml.SafeLoader.add_constructor('!env_var', _env_var_yaml)
yaml.SafeLoader.add_constructor('!secret', _secret_yaml)
yaml.SafeLoader.add_constructor('!include_dir_list', _include_dir_list_yaml)
yaml.SafeLoader.add_constructor('!include_dir_merge_list',
                                _include_dir_merge_list_yaml)
yaml.SafeLoader.add_constructor('!include_dir_named', _include_dir_named_yaml)
yaml.SafeLoader.add_constructor('!include_dir_merge_named',
                                _include_dir_merge_named_yaml)
