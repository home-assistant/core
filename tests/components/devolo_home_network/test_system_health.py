"""Tests for the devolo Home Network system health."""
import pytest

from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import configure_integration

from tests.common import get_system_health_info


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
async def test_system_health(hass: HomeAssistant):
    """Test system health."""
    await async_setup_component(hass, "system_health", {})

    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    assert info["firmware_updates_available"] is False
