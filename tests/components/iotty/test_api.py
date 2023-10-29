"""Unit tests for iottycloud API."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

logging.getLogger("iotty").setLevel(logging.DEBUG)


async def test_setup_component(hass: HomeAssistant) -> None:
    """Testing init CloudApi proxy."""

    entry = MockConfigEntry(domain="iotty", entry_id="00:00:00:00:01")
    entry.add_to_hass(hass)

    success = await async_setup_component(hass, "iotty", {})
    await hass.async_block_till_done()

    assert success is True
