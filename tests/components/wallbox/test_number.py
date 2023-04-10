"""Test Wallbox Switch component."""
import json

import pytest
import requests_mock

from homeassistant.components.input_number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.wallbox import CHARGER_MAX_CHARGING_CURRENT_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import (
    authorisation_response,
    entry,
    setup_integration,
    setup_integration_platform_not_ready,
)
from .const import MOCK_NUMBER_ENTITY_ID


async def test_wallbox_number_class(hass: HomeAssistant) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CHARGER_MAX_CHARGING_CURRENT_KEY: 20})),
            status_code=200,
        )

        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ID,
                ATTR_VALUE: 20,
            },
            blocking=True,
        )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_connection_error(hass: HomeAssistant) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CHARGER_MAX_CHARGING_CURRENT_KEY: 20})),
            status_code=404,
        )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "number",
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ID,
                    ATTR_VALUE: 20,
                },
                blocking=True,
            )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_platform_not_ready(hass: HomeAssistant) -> None:
    """Test wallbox lock not loaded on authentication error."""

    await setup_integration_platform_not_ready(hass)

    state = hass.states.get(MOCK_NUMBER_ENTITY_ID)

    assert state is None

    await hass.config_entries.async_unload(entry.entry_id)
