"""Tests for the Freebox device trackers."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .common import setup_platform

from tests.common import async_fire_time_changed


async def test_router_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    router: Mock,
) -> None:
    """Test get_hosts_list invoqued multiple times if freebox into router mode."""
    await setup_platform(hass, DEVICE_TRACKER_DOMAIN)

    assert router().lan.get_hosts_list.call_count == 2

    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert router().lan.get_hosts_list.call_count == 4


async def test_bridge_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    router_bridge_mode: Mock,
) -> None:
    """Test get_interfaces invoqued once if freebox into bridge mode."""
    await setup_platform(hass, DEVICE_TRACKER_DOMAIN)

    assert router_bridge_mode().lan.get_interfaces.call_count == 1

    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # If get_interfaces failed, not called again
    assert router_bridge_mode().lan.get_interfaces.call_count == 1


async def test_update_timeout(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    router: Mock,
) -> None:
    """Test a failing periodic update is logged once and recovers."""
    await setup_platform(hass, DEVICE_TRACKER_DOMAIN)

    router().lan.get_hosts_list.side_effect = TimeoutError
    for _ in range(2):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert "Task exception was never retrieved" not in caplog.text
    assert caplog.text.count("Error updating the Freebox") == 1

    router().lan.get_hosts_list.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "Updating the Freebox works again" in caplog.text
