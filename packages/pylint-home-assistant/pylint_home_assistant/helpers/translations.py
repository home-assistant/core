"""Helpers for reading integration translation files."""

import contextlib
from pathlib import Path
import re

import astroid
from astroid import nodes
import orjson

from .integration import get_integration_dir

_InferenceError = astroid.exceptions.InferenceError

_translations_cache: dict[str, dict | None] = {}


def clear_translations_cache() -> None:
    """Clear the translations cache (used by tests)."""
    _translations_cache.clear()


def _load_translations_from_dir(integration_dir: Path) -> dict | None:
    """Load translations from an integration directory."""
    cache_key = str(integration_dir)
    if cache_key in _translations_cache:
        return _translations_cache[cache_key]

    # Core integrations use strings.json, custom integrations use translations/en.json
    for candidate in (
        integration_dir / "strings.json",
        integration_dir / "translations" / "en.json",
    ):
        if candidate.exists():
            result: dict | None = None
            with contextlib.suppress(orjson.JSONDecodeError, OSError):
                parsed = orjson.loads(candidate.read_bytes())
                if isinstance(parsed, dict):
                    result = parsed
            _translations_cache[cache_key] = result
            return result

    _translations_cache[cache_key] = None
    return None


def load_translations(module: nodes.Module) -> dict | None:
    """Load and cache the translation data for the current integration.

    For core integrations, reads ``strings.json``.
    For custom integrations, reads ``translations/en.json``.

    Returns the parsed JSON as a dict, or ``None`` if not found.
    """
    integration_dir = get_integration_dir(module)
    if integration_dir is None:
        return None
    return _load_translations_from_dir(integration_dir)


def load_translations_for_domain(module: nodes.Module, domain: str) -> dict | None:
    """Load translations for a specific domain.

    Resolves the integration directory for *domain* relative to the
    current module's components root. This handles cases where
    ``translation_domain`` points to a different integration than the
    one currently being linted.
    """
    integration_dir = get_integration_dir(module)
    if integration_dir is None:
        return None

    # Navigate to the sibling integration directory
    components_dir = integration_dir.parent
    target_dir = components_dir / domain
    if not target_dir.is_dir():
        return None

    return _load_translations_from_dir(target_dir)


def get_exception_translations(module: nodes.Module) -> dict[str, dict]:
    """Return the ``exceptions`` section from the current integration's translations."""
    return _get_exceptions_from_data(load_translations(module))


def get_exception_translations_for_domain(
    module: nodes.Module, domain: str
) -> dict[str, dict]:
    """Return the ``exceptions`` section for a specific domain."""
    return _get_exceptions_from_data(load_translations_for_domain(module, domain))


def _get_exceptions_from_data(data: dict | None) -> dict[str, dict]:
    """Extract the exceptions section from translation data."""
    if data is None:
        return {}
    exceptions = data.get("exceptions")
    if not isinstance(exceptions, dict):
        return {}
    return exceptions


def extract_placeholder_keys(node: nodes.NodeNG | None) -> set[str] | None:
    """Extract placeholder key names from a translation_placeholders value.

    Handles inline dict literals directly. For variable references, uses
    astroid inference to resolve to the dict definition.
    Returns None if the value cannot be resolved.
    """
    if node is None:
        return None
    if isinstance(node, nodes.Dict):
        return _keys_from_dict(node)
    try:
        for inferred in node.infer():
            if isinstance(inferred, nodes.Dict):
                return _keys_from_dict(inferred)
    except _InferenceError:
        pass
    return None


def _resolve_string_key(key: nodes.NodeNG) -> str | None:
    """Resolve a dict key to a string value."""
    if isinstance(key, nodes.Const) and isinstance(key.value, str):
        return key.value
    # Try inference for constant references (e.g., CONF_DOMAIN)
    try:
        for inferred in key.infer():
            if isinstance(inferred, nodes.Const) and isinstance(inferred.value, str):
                return str(inferred.value)
    except _InferenceError:
        pass
    return None


def _keys_from_dict(node: nodes.Dict) -> set[str]:
    """Extract string keys from a Dict node.

    Handles literal string keys, constant references (e.g., ``CONF_DOMAIN``)
    via astroid inference, and ``**expr`` dict unpacking by inferring the
    unpacked expression.
    """
    keys: set[str] = set()
    for key, value in node.items:
        if isinstance(key, nodes.DictUnpack):
            # Resolve the unpacked dict to extract its keys
            try:
                for inferred in value.infer():
                    if isinstance(inferred, nodes.Dict):
                        keys.update(_keys_from_dict(inferred))
            except _InferenceError:
                pass
            continue
        resolved = _resolve_string_key(key)
        if resolved is not None:
            keys.add(resolved)
    return keys


_KEY_REF_PATTERN = re.compile(r"^\[%key:(.+)%\]$")


def resolve_translation_reference(message: str, components_dir: Path | None) -> str:
    """Resolve ``[%key:component::domain::section::key::field%]`` references.

    Returns the resolved message string, or the original if resolution fails.
    """
    match = _KEY_REF_PATTERN.match(message)
    if not match or components_dir is None:
        return message

    parts = match.group(1).split("::")
    # Expected: component::domain::section::key::field
    # or: common::section::subsection::key
    if len(parts) < 3:
        return message

    data: dict | None = None
    walk_parts: list[str] = []

    if parts[0] == "component" and len(parts) >= 4:
        data = _load_translations_from_dir(components_dir / parts[1])
        walk_parts = parts[2:]
    elif parts[0] == "common":
        # common:: references live in homeassistant/strings.json
        data = _load_translations_from_dir(components_dir.parent)
        walk_parts = parts  # walk from "common" onwards
    else:
        return message

    if data is None:
        return message

    current: dict | str = data
    for part in walk_parts:
        if not isinstance(current, dict):
            return message
        current = current.get(part, message)
    return str(current) if isinstance(current, str) else message


def get_message_placeholders(
    message: str, components_dir: Path | None = None
) -> set[str]:
    """Extract placeholder names from a translation message template.

    Resolves ``[%key:...]`` references before extracting placeholders.
    Placeholders use Python ``str.format()`` syntax: ``{name}``.
    """
    resolved = resolve_translation_reference(message, components_dir)
    return set(re.findall(r"\{(\w+)\}", resolved))
