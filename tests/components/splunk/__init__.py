"""Tests for the Splunk integration."""

from json import dumps

from homeassistant.components.splunk import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry

CONFIG = {
    CONF_TOKEN: "abc",
    CONF_HOST: "localhost",
    CONF_PORT: 8089,
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    CONF_NAME: "Test",
}

URL = f"{['http','https'][CONFIG[CONF_SSL]]}://{CONFIG[CONF_HOST]}:{CONFIG[CONF_PORT]}/services/collector/event"

RETURN_SUCCESS = dumps({"code": 0})
RETURN_BADAUTH = dumps({"code": 4})


async def setup_platform(hass):
    """Set up the Splunk platform."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
