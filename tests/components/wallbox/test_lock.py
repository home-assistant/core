"""Test Wallbox Lock component."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.lock import SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.components.wallbox.const import CHARGER_LOCKED_UNLOCKED_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import (
    authorisation_response,
    http_403_error,
    http_404_error,
    http_429_error,
    setup_integration,
)
from .const import MOCK_LOCK_ENTITY_ID

from tests.common import MockConfigEntry


async def test_wallbox_lock_class(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test wallbox lock class."""

    await setup_integration(hass, entry)

    state = hass.states.get(MOCK_LOCK_ENTITY_ID)
    assert state
    assert state.state == "unlocked"

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.lockCharger",
            new=Mock(
                return_value={"data": {"chargerData": {CHARGER_LOCKED_UNLOCKED_KEY: 1}}}
            ),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.unlockCharger",
            new=Mock(
                return_value={"data": {"chargerData": {CHARGER_LOCKED_UNLOCKED_KEY: 0}}}
            ),
        ),
    ):
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


async def test_wallbox_lock_class_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox lock class connection error."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.lockCharger",
            new=Mock(side_effect=ConnectionError),
        ),
        pytest.raises(ConnectionError),
    ):
        await hass.services.async_call(
            "lock",
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.lockCharger",
            new=Mock(side_effect=ConnectionError),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.unlockCharger",
            new=Mock(side_effect=ConnectionError),
        ),
        pytest.raises(ConnectionError),
    ):
        await hass.services.async_call(
            "lock",
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.lockCharger",
            new=Mock(side_effect=http_429_error),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.unlockCharger",
            new=Mock(side_effect=http_429_error),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "lock",
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )
    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.lockCharger",
            new=Mock(side_effect=http_403_error),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.unlockCharger",
            new=Mock(side_effect=http_403_error),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "lock",
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )
    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.lockCharger",
            new=Mock(side_effect=http_404_error),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.unlockCharger",
            new=Mock(side_effect=http_404_error),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "lock",
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )
