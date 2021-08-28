"""ruamel.yaml utility functions."""
from __future__ import annotations

from collections import OrderedDict
from contextlib import suppress
import logging
import os
from os import O_CREAT, O_TRUNC, O_WRONLY, stat_result
from typing import Union

import ruamel.yaml
from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO
from ruamel.yaml.constructor import SafeConstructor
from ruamel.yaml.error import YAMLError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import secret_yaml

_LOGGER = logging.getLogger(__name__)

JSON_TYPE = Union[list, dict, str]  # pylint: disable=invalid-name


class ExtSafeConstructor(SafeConstructor):
    """Extended SafeConstructor."""

    name: str | None = None


class UnsupportedYamlError(HomeAssistantError):
    """Unsupported YAML."""


class WriteError(HomeAssistantError):
    """Error writing the data."""


def _include_yaml(
    constructor: ExtSafeConstructor, node: ruamel.yaml.nodes.Node
) -> JSON_TYPE:
    """Load another YAML file and embeds it using the !include tag.

    Example:
        device_tracker: !include device_tracker.yaml

    """
    if constructor.name is None:
        raise HomeAssistantError(
            f"YAML include error: filename not set for {node.value}"
        )
    fname = os.path.join(os.path.dirname(constructor.name), node.value)
    return load_yaml(fname, False)


def _yaml_unsupported(
    constructor: ExtSafeConstructor, node: ruamel.yaml.nodes.Node
) -> None:
    raise UnsupportedYamlError(
        f"Unsupported YAML, you can not use {node.tag} in "
        f"{os.path.basename(constructor.name or '(None)')}"
    )


def object_to_yaml(data: JSON_TYPE) -> str:
    """Create yaml string from object."""
    yaml = YAML(typ="rt")
    yaml.indent(sequence=4, offset=2)
    stream = StringIO()
    try:
        yaml.dump(data, stream)
        result: str = stream.getvalue()
        return result
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc) from exc


def yaml_to_object(data: str) -> JSON_TYPE:
    """Create object from yaml string."""
    yaml = YAML(typ="rt")
    try:
        result: list | dict | str = yaml.load(data)
        return result
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc) from exc


def load_yaml(fname: str, round_trip: bool = False) -> JSON_TYPE:
    """Load a YAML file."""
    if round_trip:
        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True  # type: ignore[assignment]
    else:
        if ExtSafeConstructor.name is None:
            ExtSafeConstructor.name = fname
        yaml = YAML(typ="safe")
        yaml.Constructor = ExtSafeConstructor

    try:
        with open(fname, encoding="utf-8") as conf_file:
            # If configuration file is empty YAML returns None
            # We convert that to an empty dict
            return yaml.load(conf_file) or OrderedDict()
    except YAMLError as exc:
        _LOGGER.error("YAML error in %s: %s", fname, exc)
        raise HomeAssistantError(exc) from exc
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise HomeAssistantError(exc) from exc


def save_yaml(fname: str, data: JSON_TYPE) -> None:
    """Save a YAML file."""
    yaml = YAML(typ="rt")
    yaml.indent(sequence=4, offset=2)
    tmp_fname = f"{fname}__TEMP__"
    try:
        try:
            file_stat = os.stat(fname)
        except OSError:
            file_stat = stat_result((0o644, -1, -1, -1, -1, -1, -1, -1, -1, -1))
        with open(
            os.open(tmp_fname, O_WRONLY | O_CREAT | O_TRUNC, file_stat.st_mode),
            "w",
            encoding="utf-8",
        ) as temp_file:
            yaml.dump(data, temp_file)
        os.replace(tmp_fname, fname)
        if hasattr(os, "chown") and file_stat.st_ctime > -1:
            with suppress(OSError):
                os.chown(fname, file_stat.st_uid, file_stat.st_gid)
    except YAMLError as exc:
        _LOGGER.error(str(exc))
        raise HomeAssistantError(exc) from exc
    except OSError as exc:
        _LOGGER.exception("Saving YAML file %s failed: %s", fname, exc)
        raise WriteError(exc) from exc
    finally:
        if os.path.exists(tmp_fname):
            try:
                os.remove(tmp_fname)
            except OSError as exc:
                # If we are cleaning up then something else went wrong, so
                # we should suppress likely follow-on errors in the cleanup
                _LOGGER.error("YAML replacement cleanup failed: %s", exc)


ExtSafeConstructor.add_constructor("!secret", secret_yaml)
ExtSafeConstructor.add_constructor("!include", _include_yaml)
ExtSafeConstructor.add_constructor(None, _yaml_unsupported)
