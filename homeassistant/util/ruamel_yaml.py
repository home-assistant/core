"""ruamel.yaml utility functions."""
import logging
import os
from os import O_CREAT, O_TRUNC, O_WRONLY
from collections import OrderedDict
from typing import Union, List, Dict

import ruamel.yaml
from ruamel.yaml import YAML
from ruamel.yaml.constructor import SafeConstructor
from ruamel.yaml.error import YAMLError
from ruamel.yaml.compat import StringIO

from homeassistant.util.yaml import secret_yaml
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

JSON_TYPE = Union[List, Dict, str]  # pylint: disable=invalid-name


class ExtSafeConstructor(SafeConstructor):
    """Extended SafeConstructor."""


class UnsupportedYamlError(HomeAssistantError):
    """Unsupported YAML."""


class WriteError(HomeAssistantError):
    """Error writing the data."""


def _include_yaml(constructor: SafeConstructor, node: ruamel.yaml.nodes.Node) \
        -> JSON_TYPE:
    """Load another YAML file and embeds it using the !include tag.

    Example:
        device_tracker: !include device_tracker.yaml
    """
    fname = os.path.join(os.path.dirname(constructor.name), node.value)
    return load_yaml(fname, False)


def _yaml_unsupported(constructor: SafeConstructor, node:
                      ruamel.yaml.nodes.Node) -> None:
    raise UnsupportedYamlError(
        'Unsupported YAML, you can not use {} in {}'
        .format(node.tag, os.path.basename(constructor.name)))


def object_to_yaml(data: JSON_TYPE) -> str:
    """Create yaml string from object."""
    yaml = YAML(typ='rt')
    yaml.indent(sequence=4, offset=2)
    stream = StringIO()
    try:
        yaml.dump(data, stream)
        result = stream.getvalue()  # type: str
        return result
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc)


def yaml_to_object(data: str) -> JSON_TYPE:
    """Create object from yaml string."""
    yaml = YAML(typ='rt')
    try:
        result = yaml.load(data)  # type: Union[List, Dict, str]
        return result
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc)


def load_yaml(fname: str, round_trip: bool = False) -> JSON_TYPE:
    """Load a YAML file."""
    if round_trip:
        yaml = YAML(typ='rt')
        yaml.preserve_quotes = True
    else:
        ExtSafeConstructor.name = fname
        yaml = YAML(typ='safe')
        yaml.Constructor = ExtSafeConstructor

    try:
        with open(fname, encoding='utf-8') as conf_file:
            # If configuration file is empty YAML returns None
            # We convert that to an empty dict
            return yaml.load(conf_file) or OrderedDict()
    except YAMLError as exc:
        _LOGGER.error("YAML error in %s: %s", fname, exc)
        raise HomeAssistantError(exc)
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise HomeAssistantError(exc)


def save_yaml(fname: str, data: JSON_TYPE) -> None:
    """Save a YAML file."""
    yaml = YAML(typ='rt')
    yaml.indent(sequence=4, offset=2)
    tmp_fname = fname + "__TEMP__"
    try:
        file_stat = os.stat(fname)
        with open(os.open(tmp_fname, O_WRONLY | O_CREAT | O_TRUNC,
                          file_stat.st_mode), 'w', encoding='utf-8') \
                as temp_file:
            yaml.dump(data, temp_file)
        os.replace(tmp_fname, fname)
        if hasattr(os, 'chown'):
            try:
                os.chown(fname, file_stat.st_uid, file_stat.st_gid)
            except OSError:
                pass
    except YAMLError as exc:
        _LOGGER.error(str(exc))
        raise HomeAssistantError(exc)
    except OSError as exc:
        _LOGGER.exception('Saving YAML file %s failed: %s', fname, exc)
        raise WriteError(exc)
    finally:
        if os.path.exists(tmp_fname):
            try:
                os.remove(tmp_fname)
            except OSError as exc:
                # If we are cleaning up then something else went wrong, so
                # we should suppress likely follow-on errors in the cleanup
                _LOGGER.error("YAML replacement cleanup failed: %s", exc)


ExtSafeConstructor.add_constructor(u'!secret', secret_yaml)
ExtSafeConstructor.add_constructor(u'!include', _include_yaml)
ExtSafeConstructor.add_constructor(None, _yaml_unsupported)
