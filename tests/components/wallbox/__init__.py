"""Tests for the Wallbox integration."""

from http import HTTPStatus
import json

import requests_mock

from homeassistant.components.wallbox.const import (
    CHARGER_ADDED_ENERGY_KEY,
    CHARGER_ADDED_RANGE_KEY,
    CHARGER_CHARGING_POWER_KEY,
    CHARGER_CHARGING_SPEED_KEY,
    CHARGER_CURRENCY_KEY,
    CHARGER_CURRENT_VERSION_KEY,
    CHARGER_DATA_KEY,
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_LOCKED_UNLOCKED_KEY,
    CHARGER_MAX_AVAILABLE_POWER_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_NAME_KEY,
    CHARGER_PART_NUMBER_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_SOFTWARE_KEY,
    CHARGER_STATUS_ID_KEY,
)
from homeassistant.core import HomeAssistant

from .const import ERROR, STATUS, TTL, USER_ID

from tests.common import MockConfigEntry

test_response = json.loads(
    json.dumps(
        {
            CHARGER_CHARGING_POWER_KEY: 0,
            CHARGER_STATUS_ID_KEY: 193,
            CHARGER_MAX_AVAILABLE_POWER_KEY: 25.2,
            CHARGER_CHARGING_SPEED_KEY: 0,
            CHARGER_ADDED_RANGE_KEY: 150,
            CHARGER_ADDED_ENERGY_KEY: 44.697,
            CHARGER_NAME_KEY: "WallboxName",
            CHARGER_DATA_KEY: {
                CHARGER_MAX_CHARGING_CURRENT_KEY: 24,
                CHARGER_ENERGY_PRICE_KEY: 0.4,
                CHARGER_LOCKED_UNLOCKED_KEY: False,
                CHARGER_SERIAL_NUMBER_KEY: "20000",
                CHARGER_PART_NUMBER_KEY: "PLP1-0-2-4-9-002-E",
                CHARGER_SOFTWARE_KEY: {CHARGER_CURRENT_VERSION_KEY: "5.5.10"},
                CHARGER_CURRENCY_KEY: {"code": "EUR/kWh"},
            },
        }
    )
)

authorisation_response = json.loads(
    json.dumps(
        {
            "data": {
                "attributes": {
                    "token": "fakekeyhere",
                    USER_ID: 12345,
                    TTL: 145656758,
                    ERROR: "false",
                    STATUS: 200,
                }
            }
        }
    )
)


authorisation_response_unauthorised = json.loads(
    json.dumps(
        {
            "data": {
                "attributes": {
                    "token": "fakekeyhere",
                    USER_ID: 12345,
                    TTL: 145656758,
                    ERROR: "false",
                    STATUS: 404,
                }
            }
        }
    )
)


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test wallbox sensor class setup."""
    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
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
            json=json.loads(json.dumps({CHARGER_MAX_CHARGING_CURRENT_KEY: 20})),
            status_code=HTTPStatus.OK,
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class setup with a connection error."""
    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
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
            json=json.loads(json.dumps({CHARGER_MAX_CHARGING_CURRENT_KEY: 20})),
            status_code=HTTPStatus.FORBIDDEN,
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_read_only(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class setup for read only."""

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
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

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_platform_not_ready(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class setup for read only."""

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
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
            status_code=HTTPStatus.NOT_FOUND,
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
