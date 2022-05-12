"""Tests for Broadlink heartbeats."""
from unittest.mock import call, patch

from homeassistant.components.broadlink.heartbeat import BroadlinkHeartbeat
from homeassistant.util import dt

from . import get_device

from tests.common import async_fire_time_changed

DEVICE_PING = "homeassistant.components.broadlink.heartbeat.blk.ping"


async def test_heartbeat_trigger_startup(hass):
    """Test that the heartbeat is initialized with the first config entry."""
    device = get_device("Office")

    with patch(DEVICE_PING) as mock_ping:
        await device.setup_entry(hass)
        await hass.async_block_till_done()

    assert mock_ping.call_count == 1
    assert mock_ping.call_args == call(device.host)


async def test_heartbeat_ignore_oserror(hass, caplog):
    """Test that an OSError is ignored."""
    device = get_device("Office")

    with patch(DEVICE_PING, side_effect=OSError()):
        await device.setup_entry(hass)
        await hass.async_block_till_done()

    assert "Failed to send heartbeat to" in caplog.text


async def test_heartbeat_trigger_right_time(hass):
    """Test that the heartbeat is triggered at the right time."""
    device = get_device("Office")

    await device.setup_entry(hass)
    await hass.async_block_till_done()

    with patch(DEVICE_PING) as mock_ping:
        async_fire_time_changed(
            hass, dt.utcnow() + BroadlinkHeartbeat.HEARTBEAT_INTERVAL
        )
        await hass.async_block_till_done()

    assert mock_ping.call_count == 1
    assert mock_ping.call_args == call(device.host)


async def test_heartbeat_do_not_trigger_before_time(hass):
    """Test that the heartbeat is not triggered before the time."""
    device = get_device("Office")

    await device.setup_entry(hass)
    await hass.async_block_till_done()

    with patch(DEVICE_PING) as mock_ping:
        async_fire_time_changed(
            hass,
            dt.utcnow() + BroadlinkHeartbeat.HEARTBEAT_INTERVAL // 2,
        )
        await hass.async_block_till_done()

    assert mock_ping.call_count == 0


async def test_heartbeat_unload(hass):
    """Test that the heartbeat is deactivated when the last config entry is removed."""
    device = get_device("Office")

    mock_setup = await device.setup_entry(hass)
    await hass.async_block_till_done()

    await hass.config_entries.async_remove(mock_setup.entry.entry_id)
    await hass.async_block_till_done()

    with patch(DEVICE_PING) as mock_ping:
        async_fire_time_changed(
            hass, dt.utcnow() + BroadlinkHeartbeat.HEARTBEAT_INTERVAL
        )

    assert mock_ping.call_count == 0


async def test_heartbeat_do_not_unload(hass):
    """Test that the heartbeat is not deactivated until the last config entry is removed."""
    device_a = get_device("Office")
    device_b = get_device("Bedroom")

    mock_setup = await device_a.setup_entry(hass)
    await device_b.setup_entry(hass)
    await hass.async_block_till_done()

    await hass.config_entries.async_remove(mock_setup.entry.entry_id)
    await hass.async_block_till_done()

    with patch(DEVICE_PING) as mock_ping:
        async_fire_time_changed(
            hass, dt.utcnow() + BroadlinkHeartbeat.HEARTBEAT_INTERVAL
        )
        await hass.async_block_till_done()

    assert mock_ping.call_count == 1
    assert mock_ping.call_args == call(device_b.host)
