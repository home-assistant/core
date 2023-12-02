"""Tests for the Advantage Air component."""

from unittest.mock import patch, AsyncMock
from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry, load_fixture, load_json_object_fixture

TEST_SYSTEM_DATA = load_json_object_fixture("advantage_air/getSystemData.json")
TEST_SET_RESPONSE = load_json_object_fixture("advantage_air/setAircon.json")

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
    with patch(
        "homeassistant.components.advantage_air.advantage_air"
    ) as mock_advantage_air:
        mock_advantage_air.return_value.async_get = AsyncMock(
            return_value=TEST_SYSTEM_DATA
        )
        mock_advantage_air.return_value.aircon.async_update.return_value = (
            TEST_SET_RESPONSE
        )
        mock_advantage_air.return_value.things.async_update.return_value = (
            TEST_SET_RESPONSE
        )
        mock_advantage_air.return_value.lights.async_update.return_value = (
            TEST_SET_RESPONSE
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry
