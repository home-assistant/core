"""Test to check for circular imports in core components."""
import asyncio
import sys

import pytest


@pytest.mark.parametrize(
    "component",
    ("api", "auth", "camera", "config", "cloud", "http", "frontend", "websocket_api"),
)
async def test_circular_imports(component: str) -> None:
    """Test if we can detect circular dependencies of components."""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", f"import homeassistant.components.{component}"
    )
    await process.communicate()
    assert process.returncode == 0
