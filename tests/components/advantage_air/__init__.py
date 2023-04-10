"""Tests for the Advantage Air component."""

from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry, load_fixture

TEST_SYSTEM_DATA = load_fixture("advantage_air/getSystemData.json")
TEST_SET_RESPONSE = load_fixture("advantage_air/setAircon.json")

USER_INPUT = {
    CONF_IP_ADDRESS: "1.2.3.4",
    CONF_PORT: 2025,
}

TEST_SYSTEM_URL = (
    f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/getSystemData"
)
TEST_SET_URL = f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/setAircon"
TEST_SET_LIGHT_URL = (
    f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/setLights"
)
TEST_SET_THING_URL = (
    f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/setThings"
)


async def add_mock_config(hass):
    """Create a fake Advantage Air Config Entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test entry",
        unique_id="0123456",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
