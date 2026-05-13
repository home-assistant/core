"""Shared helpers for quality-scale-gated pylint checkers.

Provides utilities for reading and caching ``quality_scale.yaml`` files
from integration directories. Used by multiple checkers that verify
integrations back up their quality scale claims with actual code.

This module is NOT a pylint plugin itself (hence the ``_`` prefix).
"""

from pathlib import Path

from astroid import nodes
import yaml

_quality_scale_cache: dict[str, dict | None] = {}


def get_integration_dir(module: nodes.Module) -> str | None:
    """Return the integration directory if this module is inside one."""
    if not module.file or module.file == "<?>":
        return None

    file_path = Path(module.file)
    for parent in file_path.parents:
        if parent.parent.name == "components":
            return str(parent)

    return None


def load_quality_scale(integration_dir: str) -> dict | None:
    """Load and cache quality_scale.yaml for an integration."""
    if integration_dir in _quality_scale_cache:
        return _quality_scale_cache[integration_dir]

    qs_path = Path(integration_dir) / "quality_scale.yaml"
    result: dict | None = None
    if qs_path.exists():
        try:
            result = yaml.safe_load(qs_path.read_text())
        except yaml.YAMLError:
            return None

    _quality_scale_cache[integration_dir] = result
    return result


def quality_scale_rule_is_done(integration_dir: str, rule: str) -> bool:
    """Return True if a quality-scale rule is marked done."""
    data = load_quality_scale(integration_dir)
    if not data or not isinstance(data, dict):
        return False

    rules = data.get("rules", {})
    if not isinstance(rules, dict):
        return False

    match rules.get(rule):
        case "done":
            return True
        case {"status": "done"}:
            return True
        case _:
            return False
