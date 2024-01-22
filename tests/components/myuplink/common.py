"""Tessie common helpers for tests."""
import time
from unittest.mock import patch

from aioautomower.model import MowerAttributes, MowerList

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture

# from tests.components.husqvarna_automower.conftest import mower_list_fixture
TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"
USER_ID = "123"

TEST_TOKEN = load_fixture("jwt", DOMAIN)
TEST_MOWERLIST = load_json_value_fixture("mower.json", DOMAIN)

TEST_CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}


async def setup_platform(hass: HomeAssistant, side_effect=None):
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
            "awfwf",
            "afwfe",
            "http://example/authorize",
            "http://example/token",
        ),
    )

    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Husqvarna Automower of Erika Mustermann",
        data={
            "auth_implementation": "husqvarna_automower",
            "token": {
                "access_token": TEST_TOKEN,
                "scope": "iam:read amc:api",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "provider": "husqvarna",
                "user_id": USER_ID,
                "token_type": "Bearer",
                "expires_at": time.time() + 60 * 60 * 24,
            },
        },
        unique_id=USER_ID,
        entry_id="automower_test",
    )
    mock_entry.add_to_hass(hass)
    mower_data: MowerAttributes = test_data
    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator._async_update_data",
        return_value=mower_data,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
