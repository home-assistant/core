"""Test Wallbox Switch component."""
import pytest
import requests_mock

from homeassistant.components.input_number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID

from tests.components.wallbox import entry, setup_integration


async def test_wallbox_number_class(hass):
    """Test wallbox sensor class."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            text='{ "maxChargingCurrent":20}',
            status_code=200,
        )

        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.mock_title_max_charging_current",
                ATTR_VALUE: 20,
            },
            blocking=True,
        )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_connection_error(hass):
    """Test wallbox sensor class."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            text='{ "maxChargingCurrent":20}',
            status_code=404,
        )

        with pytest.raises(ConnectionError):

            await hass.services.async_call(
                "number",
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: "number.mock_title_max_charging_current",
                    ATTR_VALUE: 20,
                },
                blocking=True,
            )
    await hass.config_entries.async_unload(entry.entry_id)
