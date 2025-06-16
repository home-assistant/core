"""Custom loader."""

from __future__ import annotations

from io import StringIO
import os
from typing import TextIO

from annotatedyaml import YAMLException, YamlTypeError
from annotatedyaml.loader import (
    HAS_C_LOADER,
    JSON_TYPE,
    LoaderType,
    Secrets,
    add_constructor,
    load_yaml as load_annotated_yaml,
    load_yaml_dict as load_annotated_yaml_dict,
    parse_yaml as parse_annotated_yaml,
    secret_yaml as annotated_secret_yaml,
)
import yaml

from homeassistant.exceptions import HomeAssistantError

__all__ = [
    "HAS_C_LOADER",
    "JSON_TYPE",
    "Secrets",
    "YamlTypeError",
    "add_constructor",
    "load_yaml",
    "load_yaml_dict",
    "parse_yaml",
    "secret_yaml",
]


def load_yaml(
    fname: str | os.PathLike[str], secrets: Secrets | None = None
) -> JSON_TYPE | None:
    """Load a YAML file.

    If opening the file raises an OSError it will be wrapped in a HomeAssistantError,
    except for FileNotFoundError which will be re-raised.
    """
    try:
        return load_annotated_yaml(fname, secrets)
    except YAMLException as exc:
        raise HomeAssistantError(str(exc)) from exc


def load_yaml_dict(
    fname: str | os.PathLike[str], secrets: Secrets | None = None
) -> dict:
    """Load a YAML file and ensure the top level is a dict.

    Raise if the top level is not a dict.
    Return an empty dict if the file is empty.
    """
    try:
        return load_annotated_yaml_dict(fname, secrets)
    except YamlTypeError:
        raise
    except YAMLException as exc:
        raise HomeAssistantError(str(exc)) from exc


def parse_yaml(
    content: str | TextIO | StringIO, secrets: Secrets | None = None
) -> JSON_TYPE:
    """Parse YAML with the fastest available loader."""
    try:
        return parse_annotated_yaml(content, secrets)
    except YAMLException as exc:
        raise HomeAssistantError(str(exc)) from exc


def secret_yaml(loader: LoaderType, node: yaml.nodes.Node) -> JSON_TYPE:
    """Load secrets and embed it into the configuration YAML."""
    try:
        return annotated_secret_yaml(loader, node)
    except YAMLException as exc:
        raise HomeAssistantError(str(exc)) from exc
