"""Test Wallbox Lock component."""
import json

import pytest
import requests_mock

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.components.wallbox import InvalidAuth
from homeassistant.components.wallbox.const import CHARGER_STATUS_ID_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.components.wallbox import entry, setup_integration
from tests.components.wallbox.const import (
    ERROR,
    JWT,
    MOCK_SWITCH_ENTITY_ID,
    STATUS,
    TTL,
    USER_ID,
)

authorisation_response = json.loads(
    json.dumps(
        {
            JWT: "fakekeyhere",
            USER_ID: 12345,
            TTL: 145656758,
            ERROR: "false",
            STATUS: 200,
        }
    )
)


async def test_wallbox_switch_class(hass: HomeAssistant) -> None:
    """Test wallbox switch class."""

    await setup_integration(hass)

    state = hass.states.get(MOCK_SWITCH_ENTITY_ID)
    assert state
    assert state.state == "on"

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/v3/chargers/12345/remote-action",
            json=json.loads(json.dumps({CHARGER_STATUS_ID_KEY: 193})),
            status_code=200,
        )

        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
            },
            blocking=True,
        )

        await hass.services.async_call(
            "switch",
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_switch_class_connection_error(hass: HomeAssistant) -> None:
    """Test wallbox switch class connection error."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/v3/chargers/12345/remote-action",
            json=json.loads(json.dumps({CHARGER_STATUS_ID_KEY: 193})),
            status_code=404,
        )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_switch_class_authentication_error(hass: HomeAssistant) -> None:
    """Test wallbox switch class connection error."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/v3/chargers/12345/remote-action",
            json=json.loads(json.dumps({CHARGER_STATUS_ID_KEY: 193})),
            status_code=403,
        )

        with pytest.raises(InvalidAuth):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(InvalidAuth):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)
