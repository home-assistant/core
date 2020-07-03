"""Tests for the NWS weather component."""
from datetime import timedelta

import aiohttp

from homeassistant.components import nws
from homeassistant.helpers.entity_platform import PLATFORM_NOT_READY_BASE_WAIT_TIME
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.nws.const import NWS_CONFIG


async def test_alert(hass, mock_simple_nws):
    """Test that sensor sets up with an alert."""
    entry = MockConfigEntry(domain=nws.DOMAIN, data=NWS_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.xyz_alerts")

    assert state
    assert state.state == "1"


async def test_no_setup_if_faied_update(hass, mock_simple_nws):
    """Test that sensor does not set up if failed.."""
    instance = mock_simple_nws.return_value
    instance.update_alerts_all_zones.side_effect = aiohttp.ClientError
    instance.all_zones = None
    entry = MockConfigEntry(domain=nws.DOMAIN, data=NWS_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.xyz_alerts")

    assert not state

    instance.update_alerts_all_zones.side_effect = None
    instance.all_zones = {"XYZ"}
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=PLATFORM_NOT_READY_BASE_WAIT_TIME)
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.xyz_alerts")
    assert state
    assert state.state == "1"
