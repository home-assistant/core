"""Tessie common helpers for tests."""
from unittest.mock import patch

from aioautomower.model import MowerAttributes, MowerList

from homeassistant.components.husqvarna_automower.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import load_fixture, load_json_value_fixture

# from tests.components.husqvarna_automower.conftest import mower_list_fixture
TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"
USER_ID = "123"
CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

TEST_TOKEN = load_fixture("jwt", DOMAIN)
TEST_MOWERLIST = load_json_value_fixture("mower.json", DOMAIN)

TEST_CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}


async def setup_platform(hass: HomeAssistant, mock_config_entry, side_effect=None):
    """Set up the Tessie platform."""

    mowers_list = MowerList(**TEST_MOWERLIST)
    mowers = {}
    for mower in mowers_list.data:
        mowers[mower.id] = mower.attributes
    test_data = mowers
    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            CLIENT_ID,
            CLIENT_SECRET,
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )

    mock_entry = mock_config_entry
    mock_entry.add_to_hass(hass)
    mower_data: MowerAttributes = test_data
    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator._async_update_data",
        return_value=mower_data,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
