"""Tessie common helpers for tests."""

from http import HTTPStatus

from aiohttp import ClientConnectionError, ClientResponseError
from aiohttp.client import RequestInfo

from homeassistant.components.tessie.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

TEST_VEHICLES = load_fixture("vehicles.json", DOMAIN)
TEST_DATA = {CONF_ACCESS_TOKEN: "1234567890"}
URL_VEHICLES = "https://api.tessie.com/vehicles"

TEST_REQUEST_INFO = RequestInfo(
    url=URL_VEHICLES, method="GET", headers={}, real_url=URL_VEHICLES
)

ERROR_AUTH = ClientResponseError(
    request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.UNAUTHORIZED
)
ERROR_UNKNOWN = ClientResponseError(
    request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.BAD_REQUEST
)
ERROR_CONNECTION = ClientConnectionError()


async def setup_platform(hass: HomeAssistant, side_effect=None):
    """Set up the Tessie platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        unique_id=TEST_DATA[CONF_ACCESS_TOKEN],
    )
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    return mock_entry
