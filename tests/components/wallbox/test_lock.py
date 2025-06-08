"""Test Wallbox Lock component."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.lock import SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.components.wallbox.const import CHARGER_LOCKED_UNLOCKED_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import (
    authorisation_response,
    setup_integration,
    setup_integration_platform_not_ready,
    setup_integration_read_only,
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
            new=Mock(return_value={CHARGER_LOCKED_UNLOCKED_KEY: False}),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.unlockCharger",
            new=Mock(return_value={CHARGER_LOCKED_UNLOCKED_KEY: False}),
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


async def test_wallbox_lock_class_authentication_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox lock not loaded on authentication error."""

    await setup_integration_read_only(hass, entry)

    state = hass.states.get(MOCK_LOCK_ENTITY_ID)

    assert state is None


async def test_wallbox_lock_class_platform_not_ready(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox lock not loaded on authentication error."""

    await setup_integration_platform_not_ready(hass, entry)

    state = hass.states.get(MOCK_LOCK_ENTITY_ID)

    assert state is None
