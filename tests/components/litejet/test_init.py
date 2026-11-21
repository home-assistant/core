"""The tests for the litejet component."""

import pytest

from homeassistant.components.litejet.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import async_init_integration


async def test_setup_with_no_config(hass: HomeAssistant) -> None:
    """Test that nothing happens."""
    assert await async_setup_component(hass, DOMAIN, {}) is True
    assert DOMAIN not in hass.data


@pytest.mark.usefixtures("mock_litejet")
async def test_child_devices_link_to_mcp(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that light and switch devices are linked to the MCP parent device."""
    entry = await async_init_integration(hass, use_switch=True)

    parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_mcp"), entry.entry_id
    )
    assert parent is not None

    light_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_light_1"), entry.entry_id
    )
    assert light_device is not None
    assert light_device.via_device_id == parent.id

    switch_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_keypad_101"), entry.entry_id
    )
    assert switch_device is not None
    assert switch_device.via_device_id == parent.id


async def test_unload_entry(hass: HomeAssistant, mock_litejet) -> None:
    """Test being able to unload an entry."""
    entry = await async_init_integration(hass, use_switch=True, use_scene=True)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert DOMAIN not in hass.data
