"""Helpers for reading integration translation files."""

import contextlib
import json
from pathlib import Path
import re

import astroid
from astroid import nodes

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
            with contextlib.suppress(json.JSONDecodeError, OSError):
                parsed = json.loads(candidate.read_text())
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


def _keys_from_dict(node: nodes.Dict) -> set[str]:
    """Extract string keys from a Dict node."""
    return {
        key.value
        for key, _ in node.items
        if isinstance(key, nodes.Const) and isinstance(key.value, str)
    }


def get_message_placeholders(message: str) -> set[str]:
    """Extract placeholder names from a translation message template.

    Placeholders use Python ``str.format()`` syntax: ``{name}``.
    """
    return set(re.findall(r"\{(\w+)\}", message))
