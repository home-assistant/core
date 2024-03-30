"""Test Wallbox Lock component."""

import json

import pytest
import requests_mock

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.components.wallbox.const import CHARGER_STATUS_ID_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from . import authorisation_response, setup_integration
from .const import MOCK_SWITCH_ENTITY_ID

from tests.common import MockConfigEntry


async def test_wallbox_switch_class(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox switch class."""

    await setup_integration(hass, entry)

    state = hass.states.get(MOCK_SWITCH_ENTITY_ID)
    assert state
    assert state.state == "on"

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
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


async def test_wallbox_switch_class_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox switch class connection error."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
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


async def test_wallbox_switch_class_authentication_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox switch class connection error."""

    await setup_integration(hass, entry)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/v3/chargers/12345/remote-action",
            json=json.loads(json.dumps({CHARGER_STATUS_ID_KEY: 193})),
            status_code=403,
        )

        with pytest.raises(ConfigEntryAuthFailed):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(ConfigEntryAuthFailed):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)
