"""Test to check for circular imports in core components."""
import asyncio
import sys

import pytest


@pytest.mark.parametrize(
    "component",
    (
        "api",
        "auth",
        "camera",
        "cloud",
        "config",
        "device_automation",
        "diagnostics",
        "file_upload",
        "frontend",
        "homeassistant",
        "http",
        "lovelace",
        "onboarding",
        "persistent_notification",
        "repairs",
        "search",
        "sensor",
        "system_log",
        "recorder",
        "websocket_api",
    ),
)
async def test_circular_imports(component: str) -> None:
    """Test if we can detect circular dependencies of components."""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", f"import homeassistant.components.{component}"
    )
    await process.communicate()
    assert process.returncode == 0
