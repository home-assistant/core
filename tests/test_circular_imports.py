"""Test to check for circular imports in core components."""

import asyncio
import sys

import pytest

from homeassistant.bootstrap import (
    CORE_INTEGRATIONS,
    DEFAULT_INTEGRATIONS,
    STAGE_0_INTEGRATIONS,
    STAGE_1_INTEGRATIONS,
)


@pytest.mark.timeout(30)  # cloud can take > 9s
@pytest.mark.parametrize(
    "component",
    sorted(
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
    ),
)
async def test_circular_imports(component: str) -> None:
    """Check that components can be imported without circular imports."""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", f"import homeassistant.components.{component}"
    )
    await process.communicate()
    assert process.returncode == 0
