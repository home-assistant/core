"""Test Wallbox Lock component."""
import json

import pytest
import requests_mock

from homeassistant.components.lock import SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.components.wallbox import CONF_LOCKED_UNLOCKED_KEY
from homeassistant.const import ATTR_ENTITY_ID

from tests.components.wallbox import entry, setup_integration
from tests.components.wallbox.const import (
    CONF_ERROR,
    CONF_JWT,
    CONF_MOCK_LOCK_ENTITY_ID,
    CONF_STATUS,
    CONF_TTL,
    CONF_USER_ID,
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


async def test_wallbox_lock_class(hass):
    """Test wallbox lock class."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CONF_LOCKED_UNLOCKED_KEY: False})),
            status_code=200,
        )

        await hass.services.async_call(
            "lock",
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: CONF_MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )

        await hass.services.async_call(
            "lock",
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: CONF_MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_lock_class_connection_error(hass):
    """Test wallbox lock class connection error."""

    await setup_integration(hass)

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CONF_LOCKED_UNLOCKED_KEY: False})),
            status_code=404,
        )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "lock",
                SERVICE_LOCK,
                {
                    ATTR_ENTITY_ID: CONF_MOCK_LOCK_ENTITY_ID,
                },
                blocking=True,
            )

            await hass.services.async_call(
                "lock",
                SERVICE_UNLOCK,
                {
                    ATTR_ENTITY_ID: CONF_MOCK_LOCK_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)
