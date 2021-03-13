"""Tests for the myq integration."""
import json
import logging
from unittest.mock import patch

from pymyq.const import ACCOUNTS_ENDPOINT, DEVICES_ENDPOINT

from homeassistant.components.myq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the myq integration in Home Assistant."""

    devices_fixture = "myq/devices.json"
    devices_json = load_fixture(devices_fixture)
    devices_dict = json.loads(devices_json)

    def _handle_mock_api_oauth_authenticate():
        return 1234, 1800

    def _handle_mock_api_request(method, returns, url, **kwargs):
        _LOGGER.debug("URL: %s", url)
        if url == ACCOUNTS_ENDPOINT:
            _LOGGER.debug("Accounts")
            return None, {"accounts": [{"id": 1, "name": "mock"}]}
        if url == DEVICES_ENDPOINT.format(account_id=1):
            _LOGGER.debug("Devices")
            return None, devices_dict
        _LOGGER.debug("Something else")
        return None, {}

    with patch(
        "pymyq.api.API._oauth_authenticate",
        side_effect=_handle_mock_api_oauth_authenticate,
    ), patch("pymyq.api.API.request", side_effect=_handle_mock_api_request):
        entry = MockConfigEntry(
            domain=DOMAIN, data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"}
        )
        entry.add_to_hass(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    return entry
