"""Tests for the Logitech Squeezebox integration."""

from homeassistant.components.squeezebox.const import (
    DOMAIN,
    STATUS_QUERY_MAC,
    STATUS_QUERY_UUID,
    STATUS_QUERY_VERSION,
    STATUS_SENSOR_RESCAN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

# from homeassistant.setup import async_setup_component
from tests.common import MockConfigEntry

FAKE_IP = "42.42.42.42"
FAKE_MAC = "deadbeefdead"
FAKE_UUID = "deadbeefdeadbeefbeefdeafbeef42"
FAKE_PORT = 9000
FAKE_VERSION = "42.0"

FAKE_STATUS = {
    STATUS_QUERY_UUID: FAKE_UUID,
    STATUS_QUERY_MAC: FAKE_MAC,
    STATUS_QUERY_VERSION: FAKE_VERSION,
    STATUS_SENSOR_RESCAN: 1,
}


async def setup_mocked_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock ConfigEntry in Home Assistant."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_UUID,
        data={
            CONF_HOST: FAKE_IP,
            CONF_PORT: FAKE_PORT,
        },
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
