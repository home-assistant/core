"""The tests for the Ring sensor platform."""
import os
import unittest
import requests_mock
import asynctest
import asyncio
from datetime import datetime

from homeassistant.components.ring import (DOMAIN,
    DATA_RING_STICKUP_CAMS )
import homeassistant.components.ring.switch as ring
from homeassistant.components import ring as base_ring

from tests.components.ring.test_init import VALID_CONFIG
from tests.common import (
    get_test_config_dir, get_test_home_assistant, load_fixture)

from homeassistant.setup import async_setup_component


async def test_setup_platform(hass, config_entry, config):
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    # hass.data = {
    #     DATA_RING_STICKUP_CAMS: []
    # }


    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


# async def test_setup_platform(hass, config_entry, config):
#     """Test setup platform does nothing (it uses config entries)."""
#     hass.data = {
#         DATA_RING_STICKUP_CAMS: []
#     }

#     ring.setup_platform(hass, config_entry, config)

# async def test_state_attributes(hass, config_entry, config, controller):
#     """Tests the state attributes."""
#     setup_platform(hass, config_entry, config)
#     state = hass.states.get('switch.front_siren')
