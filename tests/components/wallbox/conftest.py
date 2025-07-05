"""Test fixtures for the Wallbox integration."""

from http import HTTPStatus
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from homeassistant.components.wallbox.const import (
    CHARGER_ADDED_ENERGY_KEY,
    CHARGER_ADDED_RANGE_KEY,
    CHARGER_CHARGING_POWER_KEY,
    CHARGER_CHARGING_SPEED_KEY,
    CHARGER_CURRENCY_KEY,
    CHARGER_CURRENT_VERSION_KEY,
    CHARGER_DATA_KEY,
    CHARGER_DATA_POST_L1_KEY,
    CHARGER_DATA_POST_L2_KEY,
    CHARGER_ECO_SMART_KEY,
    CHARGER_ECO_SMART_MODE_KEY,
    CHARGER_ECO_SMART_STATUS_KEY,
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_FEATURES_KEY,
    CHARGER_LOCKED_UNLOCKED_KEY,
    CHARGER_MAX_AVAILABLE_POWER_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_MAX_CHARGING_CURRENT_POST_KEY,
    CHARGER_MAX_ICP_CURRENT_KEY,
    CHARGER_NAME_KEY,
    CHARGER_PART_NUMBER_KEY,
    CHARGER_PLAN_KEY,
    CHARGER_POWER_BOOST_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_SOFTWARE_KEY,
    CHARGER_STATUS_ID_KEY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
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
        CHARGER_ECO_SMART_KEY: {
            CHARGER_ECO_SMART_STATUS_KEY: False,
            CHARGER_ECO_SMART_MODE_KEY: 0,
        },
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
        CHARGER_ECO_SMART_KEY: {
            CHARGER_ECO_SMART_STATUS_KEY: False,
            CHARGER_ECO_SMART_MODE_KEY: 0,
        },
    },
}

test_response_eco_mode = {
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
        CHARGER_ECO_SMART_KEY: {
            CHARGER_ECO_SMART_STATUS_KEY: True,
            CHARGER_ECO_SMART_MODE_KEY: 0,
        },
    },
}


test_response_full_solar = {
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
        CHARGER_ECO_SMART_KEY: {
            CHARGER_ECO_SMART_STATUS_KEY: True,
            CHARGER_ECO_SMART_MODE_KEY: 1,
        },
    },
}

test_response_no_power_boost = {
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
        CHARGER_PLAN_KEY: {CHARGER_FEATURES_KEY: []},
    },
}


http_403_error = requests.exceptions.HTTPError()
http_403_error.response = requests.Response()
http_403_error.response.status_code = HTTPStatus.FORBIDDEN
http_404_error = requests.exceptions.HTTPError()
http_404_error.response = requests.Response()
http_404_error.response.status_code = HTTPStatus.NOT_FOUND
http_429_error = requests.exceptions.HTTPError()
http_429_error.response = requests.Response()
http_429_error.response.status_code = HTTPStatus.TOO_MANY_REQUESTS

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

invalid_reauth_response = {
    "jwt": "fakekeyhere",
    "refresh_token": "refresh_fakekeyhere",
    "user_id": 12345,
    "ttl": 145656758,
    "refresh_token_ttl": 145756758,
    "error": False,
    "status": 200,
}


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return mock config entry."""
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
    return entry


@pytest.fixture
def mock_wallbox():
    """Patch Wallbox class for tests."""
    with patch("homeassistant.components.wallbox.Wallbox") as mock:
        wallbox = MagicMock()
        wallbox.authenticate = Mock(return_value=authorisation_response)
        wallbox.lockCharger = Mock(
            return_value={
                CHARGER_DATA_POST_L1_KEY: {
                    CHARGER_DATA_POST_L2_KEY: {CHARGER_LOCKED_UNLOCKED_KEY: True}
                }
            }
        )
        wallbox.unlockCharger = Mock(
            return_value={
                CHARGER_DATA_POST_L1_KEY: {
                    CHARGER_DATA_POST_L2_KEY: {CHARGER_LOCKED_UNLOCKED_KEY: True}
                }
            }
        )
        wallbox.setEnergyCost = Mock(return_value={CHARGER_ENERGY_PRICE_KEY: 0.25})
        wallbox.setMaxChargingCurrent = Mock(
            return_value={
                CHARGER_DATA_POST_L1_KEY: {
                    CHARGER_DATA_POST_L2_KEY: {
                        CHARGER_MAX_CHARGING_CURRENT_POST_KEY: True
                    }
                }
            }
        )
        wallbox.setIcpMaxCurrent = Mock(return_value={CHARGER_MAX_ICP_CURRENT_KEY: 25})
        wallbox.getChargerStatus = Mock(return_value=test_response)
        mock.return_value = wallbox
        yield wallbox


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test wallbox sensor class setup."""

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
