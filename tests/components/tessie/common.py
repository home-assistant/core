"""Tessie common helpers for tests."""

from http import HTTPStatus
from unittest.mock import patch

from aiohttp import ClientConnectionError, ClientResponseError
from aiohttp.client import RequestInfo

from homeassistant.components.tessie.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_STATE_OF_ALL_VEHICLES = load_json_object_fixture("vehicles.json", DOMAIN)
TEST_VEHICLE_STATE_ONLINE = load_json_object_fixture("online.json", DOMAIN)
TEST_VEHICLE_STATE_ASLEEP = load_json_object_fixture("asleep.json", DOMAIN)
TEST_RESPONSE = {"result": True}
TEST_RESPONSE_ERROR = {"result": False, "reason": "reason why"}

TEST_CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}
TESSIE_URL = "https://api.tessie.com/"

TEST_REQUEST_INFO = RequestInfo(
    url=TESSIE_URL, method="GET", headers={}, real_url=TESSIE_URL
)

ERROR_AUTH = ClientResponseError(
    request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.UNAUTHORIZED
)
ERROR_TIMEOUT = ClientResponseError(
    request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.REQUEST_TIMEOUT
)
ERROR_UNKNOWN = ClientResponseError(
    request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.BAD_REQUEST
)
ERROR_VIRTUAL_KEY = ClientResponseError(
    request_info=TEST_REQUEST_INFO,
    history=None,
    status=HTTPStatus.INTERNAL_SERVER_ERROR,
)
ERROR_CONNECTION = ClientConnectionError()


async def setup_platform(hass: HomeAssistant, side_effect=None):
    """Set up the Tessie platform."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tessie.get_state_of_all_vehicles",
        return_value=TEST_STATE_OF_ALL_VEHICLES,
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
