"""Common methods used across tests for envisalink."""

from homeassistant.components.envisalink import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

KEEP_ALIVE_PATCH = "pyenvisalink.DSCClient.keep_alive"
PERIODIC_PATCH = "pyenvisalink.DSCClient.periodic_zone_timer_dump"
RECONNECT_PATCH = "pyenvisalink.EnvisalinkClient.reconnect"

PARTITIONS = {1: {"name": "Partition 1"}, 2: {"name": "Partition 2"}}

ZONES = {
    1: {"name": "Zone 1", "type": "door"},
    2: {"name": "Zone 2", "type": "window"},
    3: {"name": "Zone 3", "type": "motion"},
    4: {"name": "Zone 4", "type": "smoke"},
}

CONFIG = {
    "envisalink": {
        "host": "127.0.0.1",
        "panel_type": "DSC",
        "user_name": "user",
        "password": "user",
        "partitions": PARTITIONS,
        "zones": ZONES,
    }
}


async def setup_platform(hass: HomeAssistant):
    """Set up the envisalink platform."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()
