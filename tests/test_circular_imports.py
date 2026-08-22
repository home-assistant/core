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


def _import_component(component: str) -> subprocess.CompletedProcess[str]:
    """Import a component in a clean interpreter."""
    return subprocess.run(
        [sys.executable, "-c", f"import homeassistant.components.{component}"],
        capture_output=True,
        check=False,
        text=True,
    )


@pytest.fixture(scope="session", autouse=True)
def component_imports() -> dict[str, subprocess.CompletedProcess[str]]:
    """Import every component, several interpreters at a time."""
    with ThreadPoolExecutor(max_workers=os.process_cpu_count()) as executor:
        return dict(
            zip(COMPONENTS, executor.map(_import_component, COMPONENTS), strict=True)
        )


@pytest.mark.timeout(600)  # covers importing every component in the first setup
@pytest.mark.parametrize("component", COMPONENTS)
def test_circular_imports(
    component: str,
    component_imports: dict[str, subprocess.CompletedProcess[str]],
) -> None:
    """Check that components can be imported without circular imports."""
    result = component_imports[component]
    assert result.returncode == 0, result.stderr
