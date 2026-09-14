#!/usr/bin/env python3
"""Generate the paths-filter config used by CI to detect changed integrations.

Each integration maps to its own source and test paths, plus the source paths of
every integration that (transitively) depends on it. That way a change to a
dependency, such as `twilio`, also selects its dependents, `twilio_call` and
`twilio_sms`, for testing.

Integrations listed in .core_files.yaml are skipped, as any change to those
already triggers the full test suite.
"""

from collections import defaultdict
import json
from pathlib import Path
import re

COMPONENTS_DIR = Path("homeassistant/components")
CORE_FILES = Path(".core_files.yaml")
OUTPUT_FILE = Path(".integration_paths.yaml")

CORE_COMPONENT_PATTERN = re.compile(
    r"^\s*-\s*homeassistant/components/([a-z0-9_]+)/\*\*\s*$", re.MULTILINE
)


def get_core_integrations() -> set[str]:
    """Return the integrations that trigger the full test suite."""
    return set(CORE_COMPONENT_PATTERN.findall(CORE_FILES.read_text()))


def get_dependencies() -> dict[str, list[str]]:
    """Return the dependencies of every integration."""
    return {
        manifest_path.parent.name: json.loads(manifest_path.read_text()).get(
            "dependencies", []
        )
        for manifest_path in sorted(COMPONENTS_DIR.glob("*/manifest.json"))
    }


def get_dependents(dependencies: dict[str, list[str]]) -> dict[str, set[str]]:
    """Return the transitive dependents of every integration."""
    direct: dict[str, set[str]] = defaultdict(set)
    for integration, deps in dependencies.items():
        for dep in deps:
            if dep in dependencies:
                direct[dep].add(integration)

    dependents: dict[str, set[str]] = {}
    for integration in dependencies:
        found: set[str] = set()
        queue = list(direct[integration])
        while queue:
            dependent = queue.pop()
            if dependent in found or dependent == integration:
                continue
            found.add(dependent)
            queue.extend(direct[dependent])
        dependents[integration] = found
    return dependents


def generate() -> str:
    """Generate the paths-filter config."""
    core_integrations = get_core_integrations()
    dependencies = get_dependencies()
    dependents = get_dependents(dependencies)

    lines: list[str] = []
    for integration in dependencies:
        paths = [
            f"homeassistant/components/{integration}/**",
            f"tests/components/{integration}/**",
        ]
        if integration not in core_integrations:
            # Only source changes can affect a dependent, its tests cannot.
            paths.extend(
                f"homeassistant/components/{dependent}/**"
                for dependent in sorted(dependents[integration])
            )
        lines.append(f"{integration}: [{', '.join(paths)}]")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Write the paths-filter config."""
    OUTPUT_FILE.write_text(generate())


if __name__ == "__main__":
    main()
