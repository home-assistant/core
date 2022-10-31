"""Tests for Z-Wave JS addon module."""
import pytest

from homeassistant.components.zwave_js.addon import AddonError, get_addon_manager


async def test_not_installed_raises_exception(hass, addon_not_installed):
    """Test addon not installed raises exception."""
    addon_manager = get_addon_manager(hass)

    with pytest.raises(AddonError):
        await addon_manager.async_configure_addon("/test", "123", "456", "789", "012")

    with pytest.raises(AddonError):
        await addon_manager.async_update_addon()
