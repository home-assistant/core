"""Test the UniFi Discovery init."""

from __future__ import annotations

from homeassistant.components.unifi_discovery.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import _patch_discovery


async def test_setup_starts_discovery(hass: HomeAssistant) -> None:
    """Test that async_setup starts discovery and dispatches flows."""
    with _patch_discovery():
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)

    # The scanner should have dispatched a flow for the Protect consumer
    flows = hass.config_entries.flow.async_progress_by_handler("unifiprotect")
    assert len(flows) == 1


async def test_setup_only_starts_discovery_once(hass: HomeAssistant) -> None:
    """Test that discovery is only started once even if setup is called multiple times."""
    with _patch_discovery():
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)

    flows_after_first = hass.config_entries.flow.async_progress_by_handler(
        "unifiprotect"
    )
    assert len(flows_after_first) == 1


async def test_setup_no_devices(hass: HomeAssistant) -> None:
    """Test setup with no devices found."""
    with _patch_discovery(no_device=True):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler("unifiprotect")
    assert len(flows) == 0


async def test_dependency_loads_discovery(
    hass: HomeAssistant,
) -> None:
    """Test that loading unifiprotect triggers unifi_discovery as dependency."""
    with _patch_discovery():
        assert await async_setup_component(hass, "unifiprotect", {})
        await hass.async_block_till_done(wait_background_tasks=True)

    # unifi_discovery should have been loaded as a dependency and started scanning
    flows = hass.config_entries.flow.async_progress_by_handler("unifiprotect")
    assert len(flows) == 1
