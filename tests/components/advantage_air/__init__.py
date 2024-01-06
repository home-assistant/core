"""Tests for the Advantage Air component."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_SYSTEM_DATA = load_json_object_fixture("getSystemData.json", DOMAIN)
TEST_SET_RESPONSE = None

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


def patch_get(return_value=TEST_SYSTEM_DATA, side_effect=None):
    """Patch the Advantage Air async_get method."""
    return patch(
        "homeassistant.components.advantage_air.advantage_air.async_get",
        new=AsyncMock(return_value=return_value, side_effect=side_effect),
    )


def patch_update(return_value=True, side_effect=None):
    """Patch the Advantage Air async_set method."""
    return patch(
        "homeassistant.components.advantage_air.advantage_air._endpoint.async_update",
        new=AsyncMock(return_value=return_value, side_effect=side_effect),
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
