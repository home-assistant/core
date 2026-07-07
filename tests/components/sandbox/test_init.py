"""Smoke test for the sandbox integration setup."""

from homeassistant.components.sandbox import SandboxData
from homeassistant.components.sandbox.const import DATA_SANDBOX
from homeassistant.components.sandbox.manager import SandboxManager
from homeassistant.components.sandbox.router import SandboxFlowRouter
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_installs_manager_router_and_hook(
    hass: HomeAssistant,
) -> None:
    """async_setup wires the manager/router and registers the config-entry hook."""
    assert await async_setup_component(hass, "sandbox", {})
    data = hass.data[DATA_SANDBOX]
    assert isinstance(data, SandboxData)
    assert isinstance(data.manager, SandboxManager)
    assert isinstance(data.router, SandboxFlowRouter)
    assert hass.config_entries.router is data.router
    assert data.bridges == {}
