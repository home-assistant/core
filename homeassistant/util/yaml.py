"""YAML utility functions."""
import logging
import os
import sys
import fnmatch
from collections import OrderedDict
from typing import Union, List, Dict

import yaml
try:
    import keyring
except ImportError:
    keyring = None

try:
    import credstash  # pylint: disable=import-error
except ImportError:
    credstash = None

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
_SECRET_NAMESPACE = 'homeassistant'
SECRET_YAML = 'secrets.yaml'
__SECRET_CACHE = {}  # type: Dict


class NodeListClass(list):
    """Wrapper class to be able to add attributes on a list."""

    pass


class NodeStrClass(str):
    """Wrapper class to be able to add attributes on a string."""

    pass


def _add_reference(obj, loader, node):
    """Add file reference information to an object."""
    if isinstance(obj, list):
        obj = NodeListClass(obj)
    if isinstance(obj, str):
        obj = NodeStrClass(obj)
    setattr(obj, '__config_file__', loader.name)
    setattr(obj, '__line__', node.start_mark.line)
    return obj


# pylint: disable=too-many-ancestors
class SafeLineLoader(yaml.SafeLoader):
    """Loader class that keeps track of line numbers."""

    def compose_node(self, parent: yaml.nodes.Node, index) -> yaml.nodes.Node:
        """Annotate a node with the first line it was seen."""
        last_line = self.line  # type: int
        node = super(SafeLineLoader,
                     self).compose_node(parent, index)  # type: yaml.nodes.Node
        node.__line__ = last_line + 1
        return node


def load_yaml(fname: str) -> Union[List, Dict]:
    """Load a YAML file."""
    try:
        with open(fname, encoding='utf-8') as conf_file:
            # If configuration file is empty YAML returns None
            # We convert that to an empty dict
            return yaml.load(conf_file, Loader=SafeLineLoader) or OrderedDict()
    except yaml.YAMLError as exc:
        _LOGGER.error(exc)
        raise HomeAssistantError(exc)
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise HomeAssistantError(exc)


def dump(_dict: dict) -> str:
    """Dump YAML to a string and remove null."""
    return yaml.safe_dump(
        _dict, default_flow_style=False, allow_unicode=True) \
        .replace(': null\n', ':\n')


def clear_secret_cache() -> None:
    """Clear the secret cache.

    Async friendly.
    """
    __SECRET_CACHE.clear()


def _include_yaml(loader: SafeLineLoader,
                  node: yaml.nodes.Node) -> Union[List, Dict]:
    """Load another YAML file and embeds it using the !include tag.

    Example:
        device_tracker: !include device_tracker.yaml
    """
    fname = os.path.join(os.path.dirname(loader.name), node.value)
    return _add_reference(load_yaml(fname), loader, node)


def _is_file_valid(name: str) -> bool:
    """Decide if a file is valid."""
    return not name.startswith('.')


def _find_files(directory: str, pattern: str):
    """Recursively load files in a directory."""
    for root, dirs, files in os.walk(directory, topdown=True):
        dirs[:] = [d for d in dirs if _is_file_valid(d)]
        for basename in files:
            if _is_file_valid(basename) and fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename


def _include_dir_named_yaml(loader: SafeLineLoader,
                            node: yaml.nodes.Node) -> OrderedDict:
    """Load multiple files from directory as a dictionary."""
    mapping = OrderedDict()  # type: OrderedDict
    loc = os.path.join(os.path.dirname(loader.name), node.value)
    for fname in _find_files(loc, '*.yaml'):
        filename = os.path.splitext(os.path.basename(fname))[0]
        mapping[filename] = load_yaml(fname)
    return _add_reference(mapping, loader, node)


def _include_dir_merge_named_yaml(loader: SafeLineLoader,
                                  node: yaml.nodes.Node) -> OrderedDict:
    """Load multiple files from directory as a merged dictionary."""
    mapping = OrderedDict()  # type: OrderedDict
    loc = os.path.join(os.path.dirname(loader.name), node.value)
    for fname in _find_files(loc, '*.yaml'):
        if os.path.basename(fname) == SECRET_YAML:
            continue
        loaded_yaml = load_yaml(fname)
        if isinstance(loaded_yaml, dict):
            mapping.update(loaded_yaml)
    return _add_reference(mapping, loader, node)


def _include_dir_list_yaml(loader: SafeLineLoader,
                           node: yaml.nodes.Node):
    """Load multiple files from directory as a list."""
    loc = os.path.join(os.path.dirname(loader.name), node.value)
    return [load_yaml(f) for f in _find_files(loc, '*.yaml')
            if os.path.basename(f) != SECRET_YAML]


def _include_dir_merge_list_yaml(loader: SafeLineLoader,
                                 node: yaml.nodes.Node):
    """Load multiple files from directory as a merged list."""
    loc = os.path.join(os.path.dirname(loader.name),
                       node.value)  # type: str
    merged_list = []  # type: List
    for fname in _find_files(loc, '*.yaml'):
        if os.path.basename(fname) == SECRET_YAML:
            continue
        loaded_yaml = load_yaml(fname)
        if isinstance(loaded_yaml, list):
            merged_list.extend(loaded_yaml)
    return _add_reference(merged_list, loader, node)


def _ordered_dict(loader: SafeLineLoader,
                  node: yaml.nodes.MappingNode) -> OrderedDict:
    """Load YAML mappings into an ordered dictionary to preserve key order."""
    loader.flatten_mapping(node)
    nodes = loader.construct_pairs(node)

    seen = {}  # type: Dict
    for (key, _), (child_node, _) in zip(nodes, node.value):
        line = child_node.start_mark.line

        try:
            hash(key)
        except TypeError:
            fname = getattr(loader.stream, 'name', '')
            raise yaml.MarkedYAMLError(
                context="invalid key: \"{}\"".format(key),
                context_mark=yaml.Mark(fname, 0, line, -1, None, None)
            )

        if key in seen:
            fname = getattr(loader.stream, 'name', '')
            _LOGGER.error(
                'YAML file %s contains duplicate key "%s". '
                'Check lines %d and %d.', fname, key, seen[key], line)
        seen[key] = line

    return _add_reference(OrderedDict(nodes), loader, node)


def _construct_seq(loader: SafeLineLoader, node: yaml.nodes.Node):
    """Add line number and file name to Load YAML sequence."""
    obj, = loader.construct_yaml_seq(node)
    return _add_reference(obj, loader, node)


def _env_var_yaml(loader: SafeLineLoader,
                  node: yaml.nodes.Node):
    """Load environment variables and embed it into the configuration YAML."""
    args = node.value.split()

    # Check for a default value
    if len(args) > 1:
        return os.getenv(args[0], ' '.join(args[1:]))
    elif args[0] in os.environ:
        return os.environ[args[0]]
    else:
        _LOGGER.error("Environment variable %s not defined.", node.value)
        raise HomeAssistantError(node.value)


def _load_secret_yaml(secret_path: str) -> Dict:
    """Load the secrets yaml from path."""
    secret_path = os.path.join(secret_path, SECRET_YAML)
    if secret_path in __SECRET_CACHE:
        return __SECRET_CACHE[secret_path]

    _LOGGER.debug('Loading %s', secret_path)
    try:
        secrets = load_yaml(secret_path)
        if 'logger' in secrets:
            logger = str(secrets['logger']).lower()
            if logger == 'debug':
                _LOGGER.setLevel(logging.DEBUG)
            else:
                _LOGGER.error("secrets.yaml: 'logger: debug' expected,"
                              " but 'logger: %s' found", logger)
            del secrets['logger']
    except FileNotFoundError:
        secrets = {}
    __SECRET_CACHE[secret_path] = secrets
    return secrets


# pylint: disable=protected-access
def _secret_yaml(loader: SafeLineLoader,
                 node: yaml.nodes.Node):
    """Load secrets and embed it into the configuration YAML."""
    secret_path = os.path.dirname(loader.name)
    while True:
        secrets = _load_secret_yaml(secret_path)

        if node.value in secrets:
            _LOGGER.debug("Secret %s retrieved from secrets.yaml in "
                          "folder %s", node.value, secret_path)
            return secrets[node.value]

        if secret_path == os.path.dirname(sys.path[0]):
            break  # sys.path[0] set to config/deps folder by bootstrap

        secret_path = os.path.dirname(secret_path)
        if not os.path.exists(secret_path) or len(secret_path) < 5:
            break  # Somehow we got past the .homeassistant config folder

    if keyring:
        # do some keyring stuff
        pwd = keyring.get_password(_SECRET_NAMESPACE, node.value)
        if pwd:
            _LOGGER.debug("Secret %s retrieved from keyring", node.value)
            return pwd

    global credstash  # pylint: disable=invalid-name

    if credstash:
        try:
            pwd = credstash.getSecret(node.value, table=_SECRET_NAMESPACE)
            if pwd:
                _LOGGER.debug("Secret %s retrieved from credstash", node.value)
                return pwd
        except credstash.ItemNotFound:
            pass
        except Exception:  # pylint: disable=broad-except
            # Catch if package installed and no config
            credstash = None

    _LOGGER.error("Secret %s not defined", node.value)
    raise HomeAssistantError(node.value)


yaml.SafeLoader.add_constructor('!include', _include_yaml)
yaml.SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                _ordered_dict)
yaml.SafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG, _construct_seq)
yaml.SafeLoader.add_constructor('!env_var', _env_var_yaml)
yaml.SafeLoader.add_constructor('!secret', _secret_yaml)
yaml.SafeLoader.add_constructor('!include_dir_list', _include_dir_list_yaml)
yaml.SafeLoader.add_constructor('!include_dir_merge_list',
                                _include_dir_merge_list_yaml)
yaml.SafeLoader.add_constructor('!include_dir_named', _include_dir_named_yaml)
yaml.SafeLoader.add_constructor('!include_dir_merge_named',
                                _include_dir_merge_named_yaml)


# From: https://gist.github.com/miracle2k/3184458
# pylint: disable=redefined-outer-name
def represent_odict(dump, tag, mapping, flow_style=None):
    """Like BaseRepresenter.represent_mapping but does not issue the sort()."""
    value = []
    node = yaml.MappingNode(tag, value, flow_style=flow_style)
    if dump.alias_key is not None:
        dump.represented_objects[dump.alias_key] = node
    best_style = True
    if hasattr(mapping, 'items'):
        mapping = mapping.items()
    for item_key, item_value in mapping:
        node_key = dump.represent_data(item_key)
        node_value = dump.represent_data(item_value)
        if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, yaml.ScalarNode) and
                not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if dump.default_flow_style is not None:
            node.flow_style = dump.default_flow_style
        else:
            node.flow_style = best_style
    return node


yaml.SafeDumper.add_representer(
    OrderedDict,
    lambda dumper, value:
    represent_odict(dumper, 'tag:yaml.org,2002:map', value))

yaml.SafeDumper.add_representer(
    NodeListClass,
    lambda dumper, value:
    dumper.represent_sequence('tag:yaml.org,2002:seq', value))
