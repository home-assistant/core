"""Tests for WiZ binary_sensor platform."""

import logging

from pywizlight import PilotParser

from homeassistant.components import wiz
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import FAKE_IP, FAKE_MAC, _mocked_wizlight, _patch_discovery, _patch_wizlight

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_binary_sensor_unique_id(hass: HomeAssistant) -> None:
    """Test a binary sensor unique id."""
    entry = MockConfigEntry(
        domain=wiz.DOMAIN,
        unique_id=FAKE_MAC,
        data={CONF_HOST: FAKE_IP},
    )
    entry.add_to_hass(hass)
    bulb = _mocked_wizlight(None, None, None)
    with _patch_discovery(), _patch_wizlight(device=bulb):
        await async_setup_component(hass, wiz.DOMAIN, {wiz.DOMAIN: {}})
        await hass.async_block_till_done()

    bulb.status = True
    bulb.state = PilotParser(
        {
            "mac": "a8bb50d46a1c",
            "src": "pir",
            "state": True,
        }
    )
    bulb.push_callback(bulb.state)
    await hass.async_block_till_done()

    entity_id = "binary_sensor.mock_title_occupancy"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == f"{FAKE_MAC}_occupancy"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    bulb.status = False
    bulb.state = PilotParser(
        {
            "mac": "a8bb50d46a1c",
            "src": "pir",
            "state": False,
        }
    )
    bulb.push_callback(bulb.state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
