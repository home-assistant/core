"""Smoke test for the sandbox_v2 integration setup."""

from homeassistant.components.sandbox_v2 import SandboxV2Data
from homeassistant.components.sandbox_v2.const import DATA_SANDBOX_V2
from homeassistant.components.sandbox_v2.manager import SandboxManager
from homeassistant.components.sandbox_v2.router import SandboxFlowRouter
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_installs_manager_router_and_hook(
    hass: HomeAssistant,
) -> None:
    """async_setup wires the manager/router and registers the config-entry hook."""
    assert await async_setup_component(hass, "sandbox_v2", {})
    data = hass.data[DATA_SANDBOX_V2]
    assert isinstance(data, SandboxV2Data)
    assert isinstance(data.manager, SandboxManager)
    assert isinstance(data.router, SandboxFlowRouter)
    assert hass.config_entries.router is data.router
    assert data.channels == {}
    assert data.bridges == {}
