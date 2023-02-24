"""Custom loader."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator
import fnmatch
from io import StringIO, TextIOWrapper
import logging
import os
from pathlib import Path
from typing import Any, TextIO, TypeVar, overload

import yaml

try:
    from yaml import CSafeLoader as FastestAvailableSafeLoader

    HAS_C_LOADER = True
except ImportError:
    HAS_C_LOADER = False
    from yaml import (  # type: ignore[assignment]
        SafeLoader as FastestAvailableSafeLoader,
    )

from homeassistant.exceptions import HomeAssistantError

from .const import SECRET_YAML
from .objects import Input, NodeListClass, NodeStrClass

# mypy: allow-untyped-calls, no-warn-return-any

JSON_TYPE = list | dict | str  # pylint: disable=invalid-name
_DictT = TypeVar("_DictT", bound=dict)

_LOGGER = logging.getLogger(__name__)


class Secrets:
    """Store secrets while loading YAML."""

    def __init__(self, config_dir: Path) -> None:
        """Initialize secrets."""
        self.config_dir = config_dir
        self._cache: dict[Path, dict[str, str]] = {}

    def get(self, requester_path: str, secret: str) -> str:
        """Return the value of a secret."""
        current_path = Path(requester_path)

        secret_dir = current_path
        while True:
            secret_dir = secret_dir.parent

            try:
                secret_dir.relative_to(self.config_dir)
            except ValueError:
                # We went above the config dir
                break

            secrets = self._load_secret_yaml(secret_dir)

            if secret in secrets:
                _LOGGER.debug(
                    "Secret %s retrieved from secrets.yaml in folder %s",
                    secret,
                    secret_dir,
                )
                return secrets[secret]

        raise HomeAssistantError(f"Secret {secret} not defined")

    def _load_secret_yaml(self, secret_dir: Path) -> dict[str, str]:
        """Load the secrets yaml from path."""
        if (secret_path := secret_dir / SECRET_YAML) in self._cache:
            return self._cache[secret_path]

        _LOGGER.debug("Loading %s", secret_path)
        try:
            secrets = load_yaml(str(secret_path))

            if not isinstance(secrets, dict):
                raise HomeAssistantError("Secrets is not a dictionary")

            if "logger" in secrets:
                logger = str(secrets["logger"]).lower()
                if logger == "debug":
                    _LOGGER.setLevel(logging.DEBUG)
                else:
                    _LOGGER.error(
                        (
                            "Error in secrets.yaml: 'logger: debug' expected, but"
                            " 'logger: %s' found"
                        ),
                        logger,
                    )
                del secrets["logger"]
        except FileNotFoundError:
            secrets = {}

        self._cache[secret_path] = secrets

        return secrets


class SafeLoader(FastestAvailableSafeLoader):
    """The fastest available safe loader."""

    def __init__(self, stream: Any, secrets: Secrets | None = None) -> None:
        """Initialize a safe line loader."""
        self.stream = stream
        if isinstance(stream, str):
            self.name = "<unicode string>"
        elif isinstance(stream, bytes):
            self.name = "<byte string>"
        else:
            self.name = getattr(stream, "name", "<file>")
        super().__init__(stream)
        self.secrets = secrets

    def get_name(self) -> str:
        """Get the name of the loader."""
        return self.name

    def get_stream_name(self) -> str:
        """Get the name of the stream."""
        return self.stream.name or ""


class SafeLineLoader(yaml.SafeLoader):
    """Loader class that keeps track of line numbers."""

    def __init__(self, stream: Any, secrets: Secrets | None = None) -> None:
        """Initialize a safe line loader."""
        super().__init__(stream)
        self.secrets = secrets

    def compose_node(  # type: ignore[override]
        self, parent: yaml.nodes.Node, index: int
    ) -> yaml.nodes.Node:
        """Annotate a node with the first line it was seen."""
        last_line: int = self.line
        node: yaml.nodes.Node = super().compose_node(  # type: ignore[assignment]
            parent, index
        )
        node.__line__ = last_line + 1  # type: ignore[attr-defined]
        return node

    def get_name(self) -> str:
        """Get the name of the loader."""
        return self.name

    def get_stream_name(self) -> str:
        """Get the name of the stream."""
        return getattr(self.stream, "name", "")


LoaderType = SafeLineLoader | SafeLoader


def load_yaml(fname: str, secrets: Secrets | None = None) -> JSON_TYPE:
    """Load a YAML file."""
    try:
        with open(fname, encoding="utf-8") as conf_file:
            return parse_yaml(conf_file, secrets)
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise HomeAssistantError(exc) from exc


def parse_yaml(
    content: str | TextIO | StringIO, secrets: Secrets | None = None
) -> JSON_TYPE:
    """Parse YAML with the fastest available loader."""
    if not HAS_C_LOADER:
        return _parse_yaml_pure_python(content, secrets)
    try:
        return _parse_yaml(SafeLoader, content, secrets)
    except yaml.YAMLError:
        # Loading failed, so we now load with the slow line loader
        # since the C one will not give us line numbers
        if isinstance(content, (StringIO, TextIO, TextIOWrapper)):
            # Rewind the stream so we can try again
            content.seek(0, 0)
        return _parse_yaml_pure_python(content, secrets)


def _parse_yaml_pure_python(
    content: str | TextIO | StringIO, secrets: Secrets | None = None
) -> JSON_TYPE:
    """Parse YAML with the pure python loader (this is very slow)."""
    try:
        return _parse_yaml(SafeLineLoader, content, secrets)
    except yaml.YAMLError as exc:
        _LOGGER.error(str(exc))
        raise HomeAssistantError(exc) from exc


def _parse_yaml(
    loader: type[SafeLoader] | type[SafeLineLoader],
    content: str | TextIO,
    secrets: Secrets | None = None,
) -> JSON_TYPE:
    """Load a YAML file."""
    # If configuration file is empty YAML returns None
    # We convert that to an empty dict
    return (
        yaml.load(content, Loader=lambda stream: loader(stream, secrets))
        or OrderedDict()
    )


@overload
def _add_reference(
    obj: list | NodeListClass,
    loader: LoaderType,
    node: yaml.nodes.Node,
) -> NodeListClass:
    ...


@overload
def _add_reference(
    obj: str | NodeStrClass,
    loader: LoaderType,
    node: yaml.nodes.Node,
) -> NodeStrClass:
    ...


@overload
def _add_reference(obj: _DictT, loader: LoaderType, node: yaml.nodes.Node) -> _DictT:
    ...


def _add_reference(  # type: ignore[no-untyped-def]
    obj, loader: LoaderType, node: yaml.nodes.Node
):
    """Add file reference information to an object."""
    if isinstance(obj, list):
        obj = NodeListClass(obj)
    if isinstance(obj, str):
        obj = NodeStrClass(obj)
    setattr(obj, "__config_file__", loader.get_name())
    setattr(obj, "__line__", node.start_mark.line)
    return obj


def _include_yaml(loader: LoaderType, node: yaml.nodes.Node) -> JSON_TYPE:
    """Load another YAML file and embeds it using the !include tag.

    Example:
        device_tracker: !include device_tracker.yaml

    """
    fname = os.path.join(os.path.dirname(loader.get_name()), node.value)
    try:
        return _add_reference(load_yaml(fname, loader.secrets), loader, node)
    except FileNotFoundError as exc:
        raise HomeAssistantError(
            f"{node.start_mark}: Unable to read file {fname}."
        ) from exc


def _is_file_valid(name: str) -> bool:
    """Decide if a file is valid."""
    return not name.startswith(".")


def _find_files(directory: str, pattern: str) -> Iterator[str]:
    """Recursively load files in a directory."""
    for root, dirs, files in os.walk(directory, topdown=True):
        dirs[:] = [d for d in dirs if _is_file_valid(d)]
        for basename in sorted(files):
            if _is_file_valid(basename) and fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename


def _include_dir_named_yaml(loader: LoaderType, node: yaml.nodes.Node) -> OrderedDict:
    """Load multiple files from directory as a dictionary."""
    mapping: OrderedDict = OrderedDict()
    loc = os.path.join(os.path.dirname(loader.get_name()), node.value)
    for fname in _find_files(loc, "*.yaml"):
        filename = os.path.splitext(os.path.basename(fname))[0]
        if os.path.basename(fname) == SECRET_YAML:
            continue
        mapping[filename] = load_yaml(fname, loader.secrets)
    return _add_reference(mapping, loader, node)


def _include_dir_merge_named_yaml(
    loader: LoaderType, node: yaml.nodes.Node
) -> OrderedDict:
    """Load multiple files from directory as a merged dictionary."""
    mapping: OrderedDict = OrderedDict()
    loc = os.path.join(os.path.dirname(loader.get_name()), node.value)
    for fname in _find_files(loc, "*.yaml"):
        if os.path.basename(fname) == SECRET_YAML:
            continue
        loaded_yaml = load_yaml(fname, loader.secrets)
        if isinstance(loaded_yaml, dict):
            mapping.update(loaded_yaml)
    return _add_reference(mapping, loader, node)


def _include_dir_list_yaml(
    loader: LoaderType, node: yaml.nodes.Node
) -> list[JSON_TYPE]:
    """Load multiple files from directory as a list."""
    loc = os.path.join(os.path.dirname(loader.get_name()), node.value)
    return [
        load_yaml(f, loader.secrets)
        for f in _find_files(loc, "*.yaml")
        if os.path.basename(f) != SECRET_YAML
    ]


def _include_dir_merge_list_yaml(
    loader: LoaderType, node: yaml.nodes.Node
) -> JSON_TYPE:
    """Load multiple files from directory as a merged list."""
    loc: str = os.path.join(os.path.dirname(loader.get_name()), node.value)
    merged_list: list[JSON_TYPE] = []
    for fname in _find_files(loc, "*.yaml"):
        if os.path.basename(fname) == SECRET_YAML:
            continue
        loaded_yaml = load_yaml(fname, loader.secrets)
        if isinstance(loaded_yaml, list):
            merged_list.extend(loaded_yaml)
    return _add_reference(merged_list, loader, node)


def _ordered_dict(loader: LoaderType, node: yaml.nodes.MappingNode) -> OrderedDict:
    """Load YAML mappings into an ordered dictionary to preserve key order."""
    loader.flatten_mapping(node)
    nodes = loader.construct_pairs(node)

    seen: dict = {}
    for (key, _), (child_node, _) in zip(nodes, node.value):
        line = child_node.start_mark.line

        try:
            hash(key)
        except TypeError as exc:
            fname = loader.get_stream_name()
            raise yaml.MarkedYAMLError(
                context=f'invalid key: "{key}"',
                context_mark=yaml.Mark(
                    fname, 0, line, -1, None, None  # type: ignore[arg-type]
                ),
            ) from exc

        if key in seen:
            fname = loader.get_stream_name()
            _LOGGER.warning(
                'YAML file %s contains duplicate key "%s". Check lines %d and %d',
                fname,
                key,
                seen[key],
                line,
            )
        seen[key] = line

    return _add_reference(OrderedDict(nodes), loader, node)


def _construct_seq(loader: LoaderType, node: yaml.nodes.Node) -> JSON_TYPE:
    """Add line number and file name to Load YAML sequence."""
    (obj,) = loader.construct_yaml_seq(node)
    return _add_reference(obj, loader, node)


def _env_var_yaml(loader: LoaderType, node: yaml.nodes.Node) -> str:
    """Load environment variables and embed it into the configuration YAML."""
    args = node.value.split()

    # Check for a default value
    if len(args) > 1:
        return os.getenv(args[0], " ".join(args[1:]))
    if args[0] in os.environ:
        return os.environ[args[0]]
    _LOGGER.error("Environment variable %s not defined", node.value)
    raise HomeAssistantError(node.value)


def secret_yaml(loader: LoaderType, node: yaml.nodes.Node) -> JSON_TYPE:
    """Load secrets and embed it into the configuration YAML."""
    if loader.secrets is None:
        raise HomeAssistantError("Secrets not supported in this YAML file")

    return loader.secrets.get(loader.get_name(), node.value)


def add_constructor(tag: Any, constructor: Any) -> None:
    """Add to constructor to all loaders."""
    for yaml_loader in (SafeLoader, SafeLineLoader):
        yaml_loader.add_constructor(tag, constructor)


add_constructor("!include", _include_yaml)
add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _ordered_dict)
add_constructor(yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG, _construct_seq)
add_constructor("!env_var", _env_var_yaml)
add_constructor("!secret", secret_yaml)
add_constructor("!include_dir_list", _include_dir_list_yaml)
add_constructor("!include_dir_merge_list", _include_dir_merge_list_yaml)
add_constructor("!include_dir_named", _include_dir_named_yaml)
add_constructor("!include_dir_merge_named", _include_dir_merge_named_yaml)
add_constructor("!input", Input.from_node)
