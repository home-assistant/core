"""Tests for the Wallbox integration."""

import json

import requests_mock

from homeassistant.components.wallbox.const import CONF_STATION, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

test_response = json.loads(
    '{"charging_power": 0,"max_available_power": "xx","charging_speed": 0,"added_range": "xx","added_energy": "44.697"}'
)


async def setup_integration(hass):
    """Test wallbox sensor class setup."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test_username",
            CONF_PASSWORD: "test_password",
            CONF_STATION: "12345",
        },
        entry_id="testEntry",
    )

    entry.add_to_hass(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        mock_request.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response,
            status_code=200,
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
