"""Helpers for reading integration metadata (manifest, file existence)."""

import contextlib
import json
from pathlib import Path

from astroid import nodes

from pylint_home_assistant.const import IntegrationType

# Caches keyed by integration domain.  Shared across all checkers so the
# same manifest is read at most once per pylint run.
_manifest_cache: dict[str, dict | None] = {}
_has_config_flow_cache: dict[str, bool] = {}


def clear_caches() -> None:
    """Clear all integration metadata caches (used by tests)."""
    _manifest_cache.clear()
    _has_config_flow_cache.clear()


def get_integration_dir(module: nodes.Module) -> Path | None:
    """Derive the integration directory from *module*'s file path.

    Walks up from the file until the parent directory is named
    ``components`` (or the module file root for ``custom_components``).
    Returns ``None`` when the path cannot be resolved.
    """
    if not module.file or module.file == "<?>":
        return None
    file_path = Path(module.file)
    for parent in (file_path.parent, *file_path.parents):
        if parent.parent.name in {"components", "custom_components"}:
            return parent
        # For custom_components at the repo root the parent IS custom_components
        if parent.name != "custom_components" and parent.parent.name == "":
            break
    return None


def read_manifest(module: nodes.Module) -> dict | None:
    """Read and cache ``manifest.json`` for the integration that owns *module*.

    Returns ``None`` when the manifest cannot be found or parsed.
    """
    root_name = module.name
    # Extract integration domain from module name
    parts = root_name.split(".")
    # Find the domain part — it's right after "components" or at index 1
    # for custom_components
    domain: str | None = None
    for i, part in enumerate(parts):
        if part in ("components", "custom_components") and i + 1 < len(parts):
            domain = parts[i + 1]
            break
    if domain is None:
        return None

    if domain in _manifest_cache:
        return _manifest_cache[domain]

    integration_dir = get_integration_dir(module)
    if integration_dir is None:
        _manifest_cache[domain] = None
        return None

    manifest_path = integration_dir / "manifest.json"
    result: dict | None = None
    if manifest_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            result = json.loads(manifest_path.read_text())

    _manifest_cache[domain] = result
    return result


def has_config_flow(integration: str, module: nodes.Module) -> bool:
    """Return True if the integration has a ``config_flow.py``.

    Results are cached per integration domain.  If the file path cannot be
    resolved (e.g. in tests), defaults to ``True`` so the checker still flags.
    """
    if integration in _has_config_flow_cache:
        return _has_config_flow_cache[integration]

    result = True  # default to flagging when path is unknown
    integration_dir = get_integration_dir(module)
    if integration_dir is not None:
        result = (integration_dir / "config_flow.py").exists()

    _has_config_flow_cache[integration] = result
    return result


def is_helper_integration(integration: str, module: nodes.Module) -> bool:
    """Return True if the integration has ``integration_type: helper``."""
    manifest = read_manifest(module)
    if manifest is None:
        return False
    return manifest.get("integration_type") == IntegrationType.HELPER
