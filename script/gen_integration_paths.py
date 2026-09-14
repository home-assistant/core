#!/usr/bin/env python3
"""Generate the paths-filter config used by CI to detect changed integrations.

Each integration maps to its own source and test paths, plus the source paths of
its (transitive) dependencies. That way a change to a dependency, such as
`twilio`, also selects its dependents, `twilio_call` and `twilio_sms`, for
testing.

Dependencies listed in .core_files.yaml are skipped, as any change to those
already triggers the full test suite.
"""

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


def get_transitive_dependencies(
    dependencies: dict[str, list[str]],
) -> dict[str, set[str]]:
    """Return the transitive dependencies of every integration."""
    transitive: dict[str, set[str]] = {}
    for integration, integration_dependencies in dependencies.items():
        found: set[str] = set()
        queue = list(integration_dependencies)
        while queue:
            dependency = queue.pop()
            if dependency in found or dependency == integration:
                continue
            if dependency not in dependencies:
                continue
            found.add(dependency)
            queue.extend(dependencies[dependency])
        transitive[integration] = found
    return transitive


def generate() -> str:
    """Generate the paths-filter config."""
    core_integrations = get_core_integrations()
    dependencies = get_dependencies()
    transitive = get_transitive_dependencies(dependencies)

    lines: list[str] = []
    for integration, integration_dependencies in transitive.items():
        paths = [
            f"homeassistant/components/{integration}/**",
            f"tests/components/{integration}/**",
        ]
        # Only source changes of a dependency can affect this integration, its
        # tests cannot.
        paths.extend(
            f"homeassistant/components/{dependency}/**"
            for dependency in sorted(integration_dependencies - core_integrations)
        )
        lines.append(f"{integration}: [{', '.join(paths)}]")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Write the paths-filter config."""
    OUTPUT_FILE.write_text(generate())


if __name__ == "__main__":
    main()
