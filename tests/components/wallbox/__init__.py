"""Tests for the Wallbox integration."""

from http import HTTPStatus
import json

import requests_mock

from homeassistant.components.wallbox.const import (
    CONF_ADDED_ENERGY_KEY,
    CONF_ADDED_RANGE_KEY,
    CONF_CHARGING_POWER_KEY,
    CONF_CHARGING_SPEED_KEY,
    CONF_CURRENT_VERSION_KEY,
    CONF_DATA_KEY,
    CONF_MAX_AVAILABLE_POWER_KEY,
    CONF_MAX_CHARGING_CURRENT_KEY,
    CONF_NAME_KEY,
    CONF_PART_NUMBER_KEY,
    CONF_SERIAL_NUMBER_KEY,
    CONF_SOFTWARE_KEY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_ERROR, CONF_JWT, CONF_STATUS, CONF_TTL, CONF_USER_ID

from tests.common import MockConfigEntry

test_response = json.loads(
    json.dumps(
        {
            CONF_CHARGING_POWER_KEY: 0,
            CONF_MAX_AVAILABLE_POWER_KEY: 25.2,
            CONF_CHARGING_SPEED_KEY: 0,
            CONF_ADDED_RANGE_KEY: 150,
            CONF_ADDED_ENERGY_KEY: 44.697,
            CONF_NAME_KEY: "WallboxName",
            CONF_DATA_KEY: {
                CONF_MAX_CHARGING_CURRENT_KEY: 24,
                CONF_SERIAL_NUMBER_KEY: "20000",
                CONF_PART_NUMBER_KEY: "PLP1-0-2-4-9-002-E",
                CONF_SOFTWARE_KEY: {CONF_CURRENT_VERSION_KEY: "5.5.10"},
            },
        }
    )
)

authorisation_response = json.loads(
    json.dumps(
        {
            CONF_JWT: "fakekeyhere",
            CONF_USER_ID: 12345,
            CONF_TTL: 145656758,
            CONF_ERROR: "false",
            CONF_STATUS: 200,
        }
    )
)

entry = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        CONF_STATION: "12345",
    },
    entry_id="testEntry",
)


async def setup_integration(hass):
    """Test wallbox sensor class setup."""

    entry.add_to_hass(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=HTTPStatus.OK,
        )
        mock_request.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response,
            status_code=HTTPStatus.OK,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CONF_MAX_CHARGING_CURRENT_KEY: 20})),
            status_code=HTTPStatus.OK,
        )

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_connection_error(hass):
    """Test wallbox sensor class setup with a connection error."""

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=HTTPStatus.FORBIDDEN,
        )
        mock_request.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response,
            status_code=HTTPStatus.FORBIDDEN,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CONF_MAX_CHARGING_CURRENT_KEY: 20})),
            status_code=HTTPStatus.FORBIDDEN,
        )

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_read_only(hass):
    """Test wallbox sensor class setup for read only."""

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=HTTPStatus.OK,
        )
        mock_request.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response,
            status_code=HTTPStatus.OK,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=test_response,
            status_code=HTTPStatus.FORBIDDEN,
        )

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
