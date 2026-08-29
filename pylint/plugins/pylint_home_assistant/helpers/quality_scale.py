"""Helpers for reading integration quality scale data."""

import contextlib
from pathlib import Path

from astroid import nodes
import yaml

from .integration import get_integration_dir

_quality_scale_cache: dict[str, dict | None] = {}


def clear_quality_scale_cache() -> None:
    """Clear the quality scale cache (used by tests)."""
    _quality_scale_cache.clear()


def _load_quality_scale(integration_dir: Path) -> dict | None:
    """Load and cache quality_scale.yaml for an integration."""
    cache_key = str(integration_dir)
    if cache_key in _quality_scale_cache:
        return _quality_scale_cache[cache_key]

    qs_path = integration_dir / "quality_scale.yaml"
    result: dict | None = None
    if qs_path.exists():
        with contextlib.suppress(yaml.YAMLError, OSError):
            result = yaml.safe_load(qs_path.read_text())

    _quality_scale_cache[cache_key] = result
    return result


def _get_rule_status(integration_dir: Path, rule: str) -> str | None:
    """Return the status string for a quality scale rule, or None."""
    data = _load_quality_scale(integration_dir)
    if not data or not isinstance(data, dict):
        return None

    rules = data.get("rules")
    if not isinstance(rules, dict):
        return None

    match rules.get(rule):
        case str(status):
            return status
        case {"status": str(status)}:
            return status
        case _:
            return None


def quality_scale_rule_is_done(module: nodes.Module, rule: str) -> bool:
    """Return True if a quality scale rule is marked ``done``."""
    integration_dir = get_integration_dir(module)
    if integration_dir is None:
        return False
    return _get_rule_status(integration_dir, rule) == "done"


def quality_scale_rule_is_done_or_exempt(module: nodes.Module, rule: str) -> bool:
    """Return True if a quality scale rule is marked ``done`` or ``exempt``."""
    integration_dir = get_integration_dir(module)
    if integration_dir is None:
        return False
    return _get_rule_status(integration_dir, rule) in ("done", "exempt")
