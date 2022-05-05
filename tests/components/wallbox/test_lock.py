"""Test Wallbox Lock component."""
import json

import pytest
import requests_mock

from homeassistant.components.lock import SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.components.wallbox import CHARGER_LOCKED_UNLOCKED_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.components.wallbox import (
    entry,
    setup_integration,
    setup_integration_read_only,
)
from tests.components.wallbox.const import (
    ERROR,
    JWT,
    MOCK_LOCK_ENTITY_ID,
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


async def test_wallbox_lock_class(hass: HomeAssistant) -> None:
    """Test wallbox lock class."""

    await setup_integration(hass)

    state = hass.states.get(MOCK_LOCK_ENTITY_ID)
    assert state
    assert state.state == "unlocked"

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CHARGER_LOCKED_UNLOCKED_KEY: False})),
            status_code=200,
        )

        await hass.services.async_call(
            "lock",
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )

        await hass.services.async_call(
            "lock",
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_lock_class_connection_error(hass: HomeAssistant) -> None:
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
            json=json.loads(json.dumps({CHARGER_LOCKED_UNLOCKED_KEY: False})),
            status_code=404,
        )

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "lock",
                SERVICE_LOCK,
                {
                    ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "lock",
                SERVICE_UNLOCK,
                {
                    ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_lock_class_authentication_error(hass: HomeAssistant) -> None:
    """Test wallbox lock not loaded on authentication error."""

    await setup_integration_read_only(hass)

    state = hass.states.get(MOCK_LOCK_ENTITY_ID)

    assert state is None

    await hass.config_entries.async_unload(entry.entry_id)
