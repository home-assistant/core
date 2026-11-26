#!/usr/bin/env python3
"""Generate the paths-filter config used by CI to detect changed integrations.

Each integration maps to its own source and test paths, plus the source paths of
its (transitive) dependencies. That way a change to a dependency, such as
`twilio`, also selects its dependents, `twilio_call` and `twilio_sms`, for
testing.

Integrations imported directly from the source are added as well, since
integration platforms, such as `lovelace/cast.py`, are coupled to another
integration without declaring it in the manifest.

Dependencies listed in .core_files.yaml are skipped, as any change to those
already triggers the full test suite.
"""

from collections.abc import Collection
import json
from pathlib import Path
import re

COMPONENTS_DIR = Path("homeassistant/components")
CORE_FILES = Path(".core_files.yaml")
OUTPUT_FILE = Path(".integration_paths.yaml")

CORE_COMPONENT_PATTERN = re.compile(
    r"^\s*-\s*homeassistant/components/([a-z0-9_]+)/\*\*\s*$", re.MULTILINE
)
# `from homeassistant.components.x import`, `import homeassistant.components.x`
# and `from homeassistant.components import x, y`, the latter also parenthesized
INTEGRATION_IMPORT_PATTERN = re.compile(
    r"(?:from|import)\s+homeassistant\.components\.([a-z0-9_]+)"
    r"|from\s+homeassistant\.components\s+import\s+\(?([a-z0-9_,\s]+)"
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


def get_imported_integrations(
    integrations: Collection[str],
) -> dict[str, set[str]]:
    """Return the integrations imported in the source of every integration."""
    imported: dict[str, set[str]] = {}
    for integration in integrations:
        found: set[str] = set()
        for path in sorted((COMPONENTS_DIR / integration).rglob("*.py")):
            source = path.read_text()
            if "homeassistant.components" not in source:
                continue
            for match in INTEGRATION_IMPORT_PATTERN.finditer(source):
                if module := match.group(1):
                    found.add(module)
                else:
                    found.update(name.strip() for name in match.group(2).split(","))
        imported[integration] = {
            module
            for module in found
            if module in integrations and module != integration
        }
    return imported


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
                # hassfest rejects unknown dependencies: this only guards
                # against a KeyError on a branch that hasn't been validated
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
    imported = get_imported_integrations(dependencies.keys())

    lines: list[str] = []
    for integration, integration_dependencies in transitive.items():
        paths = [
            f"homeassistant/components/{integration}/**",
            f"tests/components/{integration}/**",
        ]
        # Imports are deliberately not resolved transitively: the import graph
        # runs through the hub integrations and would select most of the
        # repository. Only source changes can affect this integration, tests
        # cannot.
        coupled = integration_dependencies | imported[integration]
        paths.extend(
            f"homeassistant/components/{dependency}/**"
            for dependency in sorted(coupled - core_integrations)
        )
        lines.append(f"{integration}: [{', '.join(paths)}]")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Write the paths-filter config."""
    OUTPUT_FILE.write_text(generate())


if __name__ == "__main__":
    main()
