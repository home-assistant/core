"""Test to check for circular imports in core components."""

from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import sys

import pytest

from homeassistant.bootstrap import (
    CORE_INTEGRATIONS,
    DEFAULT_INTEGRATIONS,
    STAGE_0_INTEGRATIONS,
    STAGE_1_INTEGRATIONS,
)

COMPONENTS = sorted(
    {
        *CORE_INTEGRATIONS,
        *(
            domain
            for name, domains, timeout in STAGE_0_INTEGRATIONS
            for domain in domains
        ),
        *STAGE_1_INTEGRATIONS,
        *DEFAULT_INTEGRATIONS,
    }
)

# Each import is a whole interpreter loading a component's dependency tree, so it
# is both CPU and memory hungry. The suite already runs one xdist worker per CPU;
# a small fixed ceiling keeps this from oversubscribing the host, and measuring
# showed nothing to gain above it.
MAX_CONCURRENT_IMPORTS = 4
IMPORT_TIMEOUT = 120


def _import_component(component: str) -> tuple[int, str]:
    """Import a component in a clean interpreter, returning its exit code."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import homeassistant.components.{component}"],
            capture_output=True,
            check=False,
            text=True,
            timeout=IMPORT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return 1, f"importing timed out after {IMPORT_TIMEOUT} seconds"
    return result.returncode, result.stderr


@pytest.fixture(scope="session", autouse=True)
def component_imports() -> dict[str, tuple[int, str]]:
    """Import every component, several interpreters at a time."""
    workers = min(MAX_CONCURRENT_IMPORTS, os.process_cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return dict(
            zip(COMPONENTS, executor.map(_import_component, COMPONENTS), strict=True)
        )


@pytest.mark.timeout(600)  # the first test imports every component
@pytest.mark.parametrize("component", COMPONENTS)
def test_circular_imports(
    component: str, component_imports: dict[str, tuple[int, str]]
) -> None:
    """Check that components can be imported without circular imports."""
    returncode, stderr = component_imports[component]
    assert returncode == 0, stderr
