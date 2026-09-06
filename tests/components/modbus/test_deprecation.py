"""Test the deprecation of get_hub."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest

from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.modbus import DATA_MODBUS_HUBS
from homeassistant.core import HomeAssistant


def _caller_in(root: Path, path: str) -> ModuleType:
    """Load a module that calls get_hub, from a file at *path*.

    The report names an integration by walking the stack for a file under
    `custom_components/` or `homeassistant/components/`, so a test of who gets
    named has to call from a file that actually sits there.
    """
    source = root / path / "caller.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "from homeassistant.components.modbus import get_hub\n"
        "\n"
        "def call(hass):\n"
        '    return get_hub(hass, "hub")\n'
    )

    spec = importlib.util.spec_from_file_location(
        f"caller_{source.parent.name}", source
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="hub")
def hub_fixture(hass: HomeAssistant) -> object:
    """Put one hub in place for get_hub to return."""
    hub = object()
    hass.data[DATA_MODBUS_HUBS] = {"hub": hub}
    return hub


async def test_a_custom_integration_is_warned(
    hass: HomeAssistant,
    hub: object,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A custom integration has its own config flow to collect details in.

    Called through the real stack, so this also covers the report reaching
    past modbus's own frame to the caller that asked.
    """
    caller = _caller_in(tmp_path, "custom_components/my_integration")

    assert caller.call(hass) is hub

    assert "deprecated" in caplog.text
    assert "async_get_unit" in caplog.text
    assert "my_integration" in caplog.text
    assert "2027.10" in caplog.text
    assert "modbus" not in caplog.text.split("my_integration")[0]


async def test_a_core_integration_is_not_warned(
    hass: HomeAssistant,
    hub: object,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Flexit is the one caller in core, and the user cannot act on it."""
    caller = _caller_in(tmp_path, "homeassistant/components/flexit")

    assert caller.call(hass) is hub

    assert "deprecated" not in caplog.text


async def test_a_caller_outside_any_integration_is_not_warned(
    hass: HomeAssistant, hub: object, caplog: pytest.LogCaptureFixture
) -> None:
    """Nothing to name and nobody to tell, so it stays quiet."""
    assert get_hub(hass, "hub") is hub

    assert "deprecated" not in caplog.text
