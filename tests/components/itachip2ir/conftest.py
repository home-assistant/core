"""Fixtures for the iTach IP2IR tests."""

from pathlib import Path
import sys
from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations."""
    return


@pytest.fixture(autouse=True)
def ensure_custom_components_path():
    """Ensure custom_components is importable."""
    root = Path(__file__).resolve().parents[1]
    homeassistant_components = root / "homeassistant.components"

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    if str(homeassistant_components) not in sys.path:
        sys.path.insert(0, str(homeassistant_components))


@pytest.fixture(autouse=True)
def disable_udp_discovery_in_tests(hass: HomeAssistant):
    """Disable UDP discovery globally."""
    hass.data["itachip2ir_disable_discovery"] = True


@pytest.fixture(autouse=True)
def mock_itach_client(monkeypatch: pytest.MonkeyPatch):
    """Mock TCP client globally."""

    class FakeClient:
        def __init__(self, host, port) -> None:
            self.host = host
            self.port = port
            self.close = AsyncMock()

        async def async_get_ir_module(self):
            return 1, 3

        async def async_get_ir_connector_modes(self, module, ports):
            return {1: "IR", 2: "SENSOR", 3: "IR_BLASTER"}

        async def async_get_version(self, module):
            return "710-1000-23"

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachClient",
        FakeClient,
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.ItachClient",
        FakeClient,
    )
