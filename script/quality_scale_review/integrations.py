"""Resolve the integration domains a pull request touches."""

from pathlib import Path
import re

_COMPONENT_PATH = re.compile(r"^(?:homeassistant|tests)/components/([a-z0-9_]+)/")
_COMPONENTS_DIR = Path("homeassistant/components")
_QUALITY_SCALE = "quality_scale.yaml"


def touched_domains(filenames: list[str]) -> list[str]:
    """Return the integration domains these changed files belong to, sorted."""
    return sorted(
        {match.group(1) for name in filenames if (match := _COMPONENT_PATH.match(name))}
    )


def with_quality_scale(
    domains: list[str],
    filenames: list[str],
    components_dir: Path = _COMPONENTS_DIR,
) -> list[str]:
    """Keep the domains whose integration has a `quality_scale.yaml`.

    The checkout is the default branch, so a quality scale that the pull
    request itself adds shows up only in its changed files.
    """
    added = {name for name in filenames if name.endswith(f"/{_QUALITY_SCALE}")}
    return [
        domain
        for domain in domains
        if (components_dir / domain / _QUALITY_SCALE).is_file()
        or f"homeassistant/components/{domain}/{_QUALITY_SCALE}" in added
    ]
