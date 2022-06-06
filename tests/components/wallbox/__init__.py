"""Tests for the Wallbox integration."""

from http import HTTPStatus
import json
from unittest.mock import Mock, patch

from requests.exceptions import HTTPError

from homeassistant.components.wallbox.const import (
    CHARGER_ADDED_ENERGY_KEY,
    CHARGER_ADDED_RANGE_KEY,
    CHARGER_CHARGING_POWER_KEY,
    CHARGER_CHARGING_SPEED_KEY,
    CHARGER_CURRENT_VERSION_KEY,
    CHARGER_DATA_KEY,
    CHARGER_LOCKED_UNLOCKED_KEY,
    CHARGER_MAX_AVAILABLE_POWER_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_NAME_KEY,
    CHARGER_PART_NUMBER_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_SOFTWARE_KEY,
    CHARGER_STATUS_ID_KEY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

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
                CHARGER_LOCKED_UNLOCKED_KEY: False,
                CHARGER_SERIAL_NUMBER_KEY: "20000",
                CHARGER_PART_NUMBER_KEY: "PLP1-0-2-4-9-002-E",
                CHARGER_SOFTWARE_KEY: {CHARGER_CURRENT_VERSION_KEY: "5.5.10"},
            },
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


async def setup_integration(hass: HomeAssistant) -> None:
    """Test wallbox sensor class setup."""

    with patch("wallbox.Wallbox.authenticate", return_value=None), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
    ), patch("wallbox.Wallbox.setMaxChargingCurrent", return_value=None,), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
    ), patch(
        "wallbox.Wallbox.unlockCharger",
        return_value=None,
    ):

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_connection_error(hass: HomeAssistant) -> None:
    """Test wallbox sensor class setup with a connection error."""

    with patch(
        "wallbox.Wallbox.authenticate",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ), patch(
        "wallbox.Wallbox.setMaxChargingCurrent",
        return_value=json.loads(json.dumps({CHARGER_MAX_CHARGING_CURRENT_KEY: 20})),
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ):

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_invalidauth_error(hass: HomeAssistant) -> None:
    """Test wallbox sensor class setup with a connection error."""

    with patch(
        "wallbox.Wallbox.authenticate",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ), patch(
        "wallbox.Wallbox.setMaxChargingCurrent",
        return_value=json.loads(json.dumps({CHARGER_MAX_CHARGING_CURRENT_KEY: 20})),
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ):

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_read_only(hass: HomeAssistant) -> None:
    """Test wallbox sensor class setup for read only."""

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
    ), patch(
        "wallbox.Wallbox.setMaxChargingCurrent",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
    ), patch(
        "wallbox.Wallbox.unlockCharger",
        return_value=None,
    ):

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_charger_status_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test wallbox sensor class setup for read only."""

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ), patch("wallbox.Wallbox.setMaxChargingCurrent", return_value=None,), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
    ), patch(
        "wallbox.Wallbox.unlockCharger",
        return_value=None,
    ):

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_no_lock_auth(hass: HomeAssistant) -> None:
    """Test wallbox sensor class setup."""

    with patch("wallbox.Wallbox.authenticate", return_value=None), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
    ), patch("wallbox.Wallbox.setMaxChargingCurrent", return_value=None,), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ), patch(
        "wallbox.Wallbox.unlockCharger",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ):

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
