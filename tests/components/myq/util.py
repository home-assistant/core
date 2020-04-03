"""Tests for the myq integration."""

import json

from asynctest import patch

from homeassistant.components.myq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


async def async_init_integration(
    hass: HomeAssistant, skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the myq integration in Home Assistant."""

    devices_fixture = "myq/devices.json"
    devices_json = load_fixture(devices_fixture)
    devices_dict = json.loads(devices_json)

    def _handle_mock_api_request(method, endpoint, **kwargs):
        if endpoint == "Login":
            return {"SecurityToken": 1234}
        elif endpoint == "My":
            return {"Account": {"Id": 1}}
        elif endpoint == "Accounts/1/Devices":
            return devices_dict
        return {}

    with patch("pymyq.api.API.request", side_effect=_handle_mock_api_request):
        entry = MockConfigEntry(
            domain=DOMAIN, data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"}
        )
        entry.add_to_hass(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    return entry
