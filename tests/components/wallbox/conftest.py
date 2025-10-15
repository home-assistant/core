"""Test fixtures for the Wallbox integration."""

from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from homeassistant.components.wallbox.const import (
    CHARGER_DATA_POST_L1_KEY,
    CHARGER_DATA_POST_L2_KEY,
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_JWT_REFRESH_TOKEN,
    CHARGER_JWT_REFRESH_TTL,
    CHARGER_JWT_TOKEN,
    CHARGER_JWT_TTL,
    CHARGER_LOCKED_UNLOCKED_KEY,
    CHARGER_MAX_CHARGING_CURRENT_POST_KEY,
    CHARGER_MAX_ICP_CURRENT_KEY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import WALLBOX_AUTHORISATION_RESPONSE, WALLBOX_STATUS_RESPONSE

from tests.common import MockConfigEntry

http_403_error = requests.exceptions.HTTPError()
http_403_error.response = requests.Response()
http_403_error.response.status_code = HTTPStatus.FORBIDDEN
http_404_error = requests.exceptions.HTTPError()
http_404_error.response = requests.Response()
http_404_error.response.status_code = HTTPStatus.NOT_FOUND
http_429_error = requests.exceptions.HTTPError()
http_429_error.response = requests.Response()
http_429_error.response.status_code = HTTPStatus.TOO_MANY_REQUESTS


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test_username",
            CONF_PASSWORD: "test_password",
            CONF_STATION: "12345",
            CHARGER_JWT_TOKEN: "test_token",
            CHARGER_JWT_REFRESH_TOKEN: "test_refresh_token",
            CHARGER_JWT_TTL: (
                datetime.timestamp(datetime.now() + timedelta(hours=1)) * 1000
            ),
            CHARGER_JWT_REFRESH_TTL: (
                datetime.timestamp(datetime.now() + timedelta(hours=1)) * 1000
            ),
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
        wallbox.authenticate = Mock(return_value=WALLBOX_AUTHORISATION_RESPONSE)
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
        wallbox.getChargerStatus = Mock(return_value=WALLBOX_STATUS_RESPONSE)
        mock.return_value = wallbox
        yield wallbox


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test wallbox sensor class setup."""

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
