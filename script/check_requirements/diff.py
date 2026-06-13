"""Parse a unified diff for changes to requirements files."""

from dataclasses import dataclass
from fnmatch import fnmatchcase
import re

from unidiff import PatchSet

from .models import PackageChange

# Glob patterns; kept in sync with the `paths:`
# filter of the deterministic workflow in
# `.github/workflows/check-requirements-deterministic.yml`.
# `pyproject.toml` is intentionally NOT tracked: hassfest enforces that
# every dependency declared there is mirrored into the generated
# requirements files, so the requirements files are the single source
# of truth for pinned package changes.
TRACKED_PATTERNS = (
    "requirements*.txt",
    "homeassistant/package_constraints.txt",
)


def _is_tracked(path: str) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in TRACKED_PATTERNS)


_PIN_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?:\[[A-Za-z0-9,_-]+\])?"
    r"\s*==\s*"
    r"([A-Za-z0-9][A-Za-z0-9.+!*-]*)"
)


def _normalize(name: str) -> str:
    """PEP 503 canonical name."""
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass(slots=True, frozen=True)
class _Pin:
    name: str  # PEP 503 canonical
    raw_name: str  # original casing
    version: str


def _parse_pin(line: str) -> _Pin | None:
    body = line.split(";", 1)[0].strip()
    m = _PIN_RE.match(body)
    if not m:
        return None
    return _Pin(name=_normalize(m.group(1)), raw_name=m.group(1), version=m.group(2))


def parse_diff(diff_text: str) -> list[PackageChange]:
    """Return one PackageChange per package whose exact-pin changed in the diff.

    A package that appears in both '-' and '+' is a bump; only in '+' is new.
    """
    added: dict[str, _Pin] = {}
    removed: dict[str, _Pin] = {}
    for patched_file in PatchSet(diff_text):
        if not _is_tracked(patched_file.path):
            continue
        for hunk in patched_file:
            for line in hunk:
                if not (line.is_added or line.is_removed):
                    continue
                pin = _parse_pin(line.value)
                if pin is None:
                    continue
                bucket = added if line.is_added else removed
                bucket.setdefault(pin.name, pin)

    changes: list[PackageChange] = []
    for name, add in added.items():
        rem = removed.get(name)
        if rem is None:
            changes.append(
                PackageChange(
                    name=add.raw_name,
                    old_version=None,
                    new_version=add.version,
                )
            )
        elif rem.version != add.version:
            changes.append(
                PackageChange(
                    name=add.raw_name,
                    old_version=rem.version,
                    new_version=add.version,
                )
            )
    return sorted(changes, key=lambda c: c.name.lower())
