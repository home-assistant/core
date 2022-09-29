"""Tests for the LIFX sensor platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components import lifx
from homeassistant.components.lifx import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    SERIAL,
    _mocked_extended_multizone_strip,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def patch_lifx_state_settle_delay():
    """Set asyncio.sleep for state settles to zero."""
    with patch("homeassistant.components.lifx.light.LIFX_STATE_SETTLE_DELAY", 0):
        yield


async def test_multizone_zones_sensor(hass: HomeAssistant) -> None:
    """Test the multizone zones sensor."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_extended_multizone_strip()

    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    entity_id = "sensor.my_bulb_zones"
    assert bulb.zones_count == 8
    assert len(bulb.color_zones) == 8
    assert hass.states.get(entity_id).state == "8"
