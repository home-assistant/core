"""Tessie common helpers for tests."""

from http import HTTPStatus
from unittest.mock import patch, AsyncMock, MagicMock

from aiohttp import ClientConnectionError, ClientResponseError

from homeassistant.components.tessie.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

TEST_VEHICLES = load_fixture("vehicles.json", DOMAIN)
TEST_DATA = {CONF_API_KEY: "1234567890"}
URL_VEHICLES = "https://api.tessie.com/vehicles"

ERROR_AUTH = ClientResponseError(
    request_info=None, history=None, status=HTTPStatus.UNAUTHORIZED
)
ERROR_UNKNOWN = ClientResponseError(
    request_info=None, history=None, status=HTTPStatus.BAD_REQUEST
)
ERROR_CONNECTION = ClientConnectionError()


async def setup_platform(hass: HomeAssistant, side_effect=None):
    """Set up the Tessie platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        unique_id=TEST_DATA[CONF_API_KEY],
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "tessie_api.current_state.get_state_of_all_vehicles",
        return_value=TEST_VEHICLES,
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
