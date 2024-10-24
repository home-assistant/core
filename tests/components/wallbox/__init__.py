"""Tests for the Wallbox integration."""

from http import HTTPStatus

import requests_mock

from homeassistant.components.wallbox.const import (
    CHARGER_ADDED_ENERGY_KEY,
    CHARGER_ADDED_RANGE_KEY,
    CHARGER_ATTRIBUTES_KEY,
    CHARGER_CHARGER_KEY,
    CHARGER_CHARGER_NAME_KEY,
    CHARGER_CHARGING_POWER_KEY,
    CHARGER_CHARGING_SPEED_KEY,
    CHARGER_COST_KEY,
    CHARGER_CURRENCY_KEY,
    CHARGER_CURRENT_VERSION_KEY,
    CHARGER_DATA_KEY,
    CHARGER_DISCHARGED_ENERGY_KEY,
    CHARGER_DISCHARGING_TIME_KEY,
    CHARGER_END_KEY,
    CHARGER_ENERGY_KEY,
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_FEATURES_KEY,
    CHARGER_GREEN_ENERGY_KEY,
    CHARGER_GROUP_KEY,
    CHARGER_ID_KEY,
    CHARGER_LINKS_KEY,
    CHARGER_LOCKED_UNLOCKED_KEY,
    CHARGER_MAX_AVAILABLE_POWER_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_MAX_ICP_CURRENT_KEY,
    CHARGER_META_KEY,
    CHARGER_MID_ENERGY_KEY,
    CHARGER_NAME_KEY,
    CHARGER_PART_NUMBER_KEY,
    CHARGER_PLAN_KEY,
    CHARGER_POWER_BOOST_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_SESSION_DATA_KEY,
    CHARGER_SOFTWARE_KEY,
    CHARGER_START_KEY,
    CHARGER_STATUS_ID_KEY,
    CHARGER_TIME_KEY,
    CHARGER_TYPE_KEY,
    CHARGER_USER_EMAIL_KEY,
    CHARGER_USER_KEY,
    CHARGER_USERNAME_KEY,
)
from homeassistant.core import HomeAssistant

from .const import ERROR, REFRESH_TOKEN_TTL, STATUS, TTL, USER_ID

from tests.common import MockConfigEntry

test_response = {
    CHARGER_CHARGING_POWER_KEY: 0,
    CHARGER_STATUS_ID_KEY: 193,
    CHARGER_MAX_AVAILABLE_POWER_KEY: 25.0,
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
        CHARGER_MAX_ICP_CURRENT_KEY: 20,
        CHARGER_PLAN_KEY: {CHARGER_FEATURES_KEY: [CHARGER_POWER_BOOST_KEY]},
    },
}

test_response_bidir = {
    CHARGER_CHARGING_POWER_KEY: 0,
    CHARGER_STATUS_ID_KEY: 193,
    CHARGER_MAX_AVAILABLE_POWER_KEY: 25.0,
    CHARGER_CHARGING_SPEED_KEY: 0,
    CHARGER_ADDED_RANGE_KEY: 150,
    CHARGER_ADDED_ENERGY_KEY: 44.697,
    CHARGER_NAME_KEY: "WallboxName",
    CHARGER_DATA_KEY: {
        CHARGER_MAX_CHARGING_CURRENT_KEY: 24,
        CHARGER_ENERGY_PRICE_KEY: 0.4,
        CHARGER_LOCKED_UNLOCKED_KEY: False,
        CHARGER_SERIAL_NUMBER_KEY: "20000",
        CHARGER_PART_NUMBER_KEY: "QSP1-0-2-4-9-002-E",
        CHARGER_SOFTWARE_KEY: {CHARGER_CURRENT_VERSION_KEY: "5.5.10"},
        CHARGER_CURRENCY_KEY: {"code": "EUR/kWh"},
        CHARGER_MAX_ICP_CURRENT_KEY: 20,
        CHARGER_PLAN_KEY: {CHARGER_FEATURES_KEY: [CHARGER_POWER_BOOST_KEY]},
    },
}

test_response_sessions = {
    CHARGER_META_KEY: {"count": 2},
    CHARGER_LINKS_KEY: {
        "self": "http://wallbox-api.prod.wall-box.com/v4/sessions/stats?charger=12345&end_date=1728589774.205203&start_date=1725997774.205194&limit=1000&offset=0"
    },
    CHARGER_SESSION_DATA_KEY: [
        {
            CHARGER_TYPE_KEY: "charger_log_session",
            CHARGER_ID_KEY: "123456789",
            CHARGER_ATTRIBUTES_KEY: {
                CHARGER_GROUP_KEY: 12345,
                CHARGER_CHARGER_KEY: 12345,
                CHARGER_USER_KEY: 12345,
                CHARGER_START_KEY: 1728417604,
                CHARGER_END_KEY: 1728539458,
                CHARGER_ENERGY_KEY: 15.06,
                CHARGER_DISCHARGED_ENERGY_KEY: 0,
                CHARGER_MID_ENERGY_KEY: 0,
                CHARGER_GREEN_ENERGY_KEY: 0,
                CHARGER_TIME_KEY: 13577,
                CHARGER_DISCHARGING_TIME_KEY: 0,
                CHARGER_COST_KEY: 6.024,
                "cost_savings": 0,
                "cost_unit": "€",
                CHARGER_CURRENCY_KEY: {
                    "id": 1,
                    "name": "Euro Member Countries",
                    "symbol": "€",
                    "code": "EUR",
                },
                "range": 125,
                "group_name": "Family",
                "base_group_name": "Family",
                CHARGER_CHARGER_NAME_KEY: "Commander 2 SN 12345",
                "user_subgroup": "Family",
                CHARGER_USERNAME_KEY: "user",
                CHARGER_USER_EMAIL_KEY: "test.test@test.com",
                "user_rfid": None,
                "user_is_rfid": 0,
                "user_plate": None,
                "user_extra_information": None,
                "energy_unit": "kWh",
                "amount": None,
                "service_price": None,
                "service_time": None,
                "tax_rate": None,
                "tax_sales": None,
            },
        },
        {
            CHARGER_TYPE_KEY: "charger_log_session",
            CHARGER_ID_KEY: "987654321",
            CHARGER_ATTRIBUTES_KEY: {
                CHARGER_GROUP_KEY: 12345,
                CHARGER_CHARGER_KEY: 12345,
                CHARGER_USER_KEY: 12345,
                CHARGER_START_KEY: 1728331202,
                CHARGER_END_KEY: 1728366534,
                CHARGER_ENERGY_KEY: 16.139,
                CHARGER_DISCHARGED_ENERGY_KEY: 0,
                CHARGER_MID_ENERGY_KEY: 0,
                CHARGER_GREEN_ENERGY_KEY: 0,
                CHARGER_TIME_KEY: 14480,
                CHARGER_DISCHARGING_TIME_KEY: 0,
                CHARGER_COST_KEY: 6.4556,
                "cost_savings": 0,
                "cost_unit": "€",
                "currency": {
                    "id": 1,
                    "name": "Euro Member Countries",
                    "symbol": "€",
                    "code": "EUR",
                },
                "range": 134,
                "group_name": "Family",
                "base_group_name": "Family",
                CHARGER_CHARGER_NAME_KEY: "Commander 2 SN 12345",
                "user_subgroup": "Family",
                CHARGER_USERNAME_KEY: "test",
                CHARGER_USER_EMAIL_KEY: "test.test@test.com",
                "user_rfid": None,
                "user_is_rfid": 0,
                "user_plate": None,
                "user_extra_information": None,
                "energy_unit": "kWh",
                "amount": None,
                "service_price": None,
                "service_time": None,
                "tax_rate": None,
                "tax_sales": None,
            },
        },
    ],
}

test_response_sessions_empty = {
    CHARGER_META_KEY: {"count": 0},
    CHARGER_LINKS_KEY: {
        "self": "http://wallbox-api.prod.wall-box.com/v4/sessions/stats?charger=12345&end_date=1728589774.205203&start_date=1725997774.205194&limit=1000&offset=0"
    },
    CHARGER_SESSION_DATA_KEY: [],
}

authorisation_response = {
    "data": {
        "attributes": {
            "token": "fakekeyhere",
            "refresh_token": "refresh_fakekeyhere",
            USER_ID: 12345,
            TTL: 145656758,
            REFRESH_TOKEN_TTL: 145756758,
            ERROR: "false",
            STATUS: 200,
        }
    }
}


authorisation_response_unauthorised = {
    "data": {
        "attributes": {
            "token": "fakekeyhere",
            "refresh_token": "refresh_fakekeyhere",
            USER_ID: 12345,
            TTL: 145656758,
            REFRESH_TOKEN_TTL: 145756758,
            ERROR: "false",
            STATUS: 404,
        }
    }
}


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
        mock_request.get(
            "https://api.wall-box.com/v4/sessions/stats",
            json=test_response_sessions,
            status_code=HTTPStatus.OK,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json={CHARGER_MAX_CHARGING_CURRENT_KEY: 20},
            status_code=HTTPStatus.OK,
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_no_sessions(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
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
        mock_request.get(
            "https://api.wall-box.com/v4/sessions/stats",
            json=test_response_sessions_empty,
            status_code=HTTPStatus.OK,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json={CHARGER_MAX_CHARGING_CURRENT_KEY: 20},
            status_code=HTTPStatus.OK,
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_bidir(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test wallbox sensor class setup."""
    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=HTTPStatus.OK,
        )
        mock_request.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response_bidir,
            status_code=HTTPStatus.OK,
        )
        mock_request.get(
            "https://api.wall-box.com/v4/sessions/stats",
            json=test_response_sessions,
            status_code=HTTPStatus.OK,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json={CHARGER_MAX_CHARGING_CURRENT_KEY: 20},
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
        mock_request.get(
            "https://api.wall-box.com/v4/sessions/stats",
            json=test_response_sessions,
            status_code=HTTPStatus.FORBIDDEN,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json={CHARGER_MAX_CHARGING_CURRENT_KEY: 20},
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
        mock_request.get(
            "https://api.wall-box.com/v4/sessions/stats",
            json=test_response_sessions,
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
        mock_request.get(
            "https://api.wall-box.com/v4/sessions/stats",
            json=test_response_sessions,
            status_code=HTTPStatus.OK,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=test_response,
            status_code=HTTPStatus.NOT_FOUND,
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
