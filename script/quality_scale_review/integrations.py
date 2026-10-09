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
    file_statuses: dict[str, str],
    components_dir: Path = _COMPONENTS_DIR,
) -> list[str]:
    """Keep the domains whose integration has a `quality_scale.yaml` at the head.

    The checkout is the default branch, so when the pull request itself changes
    a quality scale, its GitHub API status tells whether the file still exists.
    """

    def has_quality_scale(domain: str) -> bool:
        status = file_statuses.get(
            f"homeassistant/components/{domain}/{_QUALITY_SCALE}"
        )
        if status is None:
            return (components_dir / domain / _QUALITY_SCALE).is_file()
        return status != "removed"

    return [domain for domain in domains if has_quality_scale(domain)]
