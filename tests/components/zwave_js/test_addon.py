"""Tests for Z-Wave JS addon module."""
import pytest

from homeassistant.components.zwave_js.addon import AddonError, get_addon_manager
from homeassistant.components.zwave_js.const import (
    CONF_ADDON_DEVICE,
    CONF_ADDON_S0_LEGACY_KEY,
    CONF_ADDON_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S2_UNAUTHENTICATED_KEY,
)


async def test_not_installed_raises_exception(hass, addon_not_installed):
    """Test addon not installed raises exception."""
    addon_manager = get_addon_manager(hass)

    addon_config = {
        CONF_ADDON_DEVICE: "/test",
        CONF_ADDON_S0_LEGACY_KEY: "123",
        CONF_ADDON_S2_ACCESS_CONTROL_KEY: "456",
        CONF_ADDON_S2_AUTHENTICATED_KEY: "789",
        CONF_ADDON_S2_UNAUTHENTICATED_KEY: "012",
    }

    with pytest.raises(AddonError):
        await addon_manager.async_configure_addon(addon_config)

    with pytest.raises(AddonError):
        await addon_manager.async_update_addon()
