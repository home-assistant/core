"""Test to check for circular imports in core components."""
import asyncio
import sys

import pytest


@pytest.mark.parametrize(
    "component",
    (
        "api",
        "application_credentials",
        "auth",
        "automation",
        "backup",
        "bluetooth",
        "camera",
        "cloud",
        "config",
        "counter",
        "device_automation",
        "dhcp",
        "diagnostics",
        "file_upload",
        "frontend",
        "frontend",
        "hardware",
        "hassio",
        "homeassistant",
        "http",
        "input_boolean",
        "input_button",
        "input_datetime",
        "input_number",
        "input_select",
        "input_text",
        "logger",
        "logger",
        "lovelace",
        "mqtt_eventstream",
        "network",
        "onboarding",
        "persistent_notification",
        "person",
        "recorder",
        "repairs",
        "scene",
        "schedule",
        "script",
        "search",
        "sensor",
        "sentry",
        "ssdp",
        "system_health",
        "system_log",
        "tag",
        "timer",
        "usb",
        "websocket_api",
        "zeroconf",
        "zone",
    ),
)
async def test_circular_imports(component: str) -> None:
    """Test if we can detect circular dependencies of components."""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", f"import homeassistant.components.{component}"
    )
    await process.communicate()
    assert process.returncode == 0
