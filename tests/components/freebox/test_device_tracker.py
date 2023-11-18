"""Tests for the Freebox sensors."""
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_platform

from tests.common import async_fire_time_changed


async def test_get_hosts_list(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    router_bridge_mode: Mock,
) -> None:
    """Test get_hosts_list invoqued once if freebox into bridge mode."""
    await setup_platform(hass, SENSOR_DOMAIN)

    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # If get_hosts_list failed, not called again
    assert router_bridge_mode().lan.get_hosts_list.call_count == 1
