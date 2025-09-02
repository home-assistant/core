"""Test Wallbox Lock component."""

from unittest.mock import patch

import pytest

from homeassistant.components.lock import SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.components.wallbox.coordinator import InsufficientRights
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import http_403_error, http_404_error, http_429_error, setup_integration
from .const import MOCK_LOCK_ENTITY_ID

from tests.common import MockConfigEntry


async def test_wallbox_lock_class(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox lock class."""

    await setup_integration(hass, entry)

    state = hass.states.get(MOCK_LOCK_ENTITY_ID)
    assert state
    assert state.state == "unlocked"

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


async def test_wallbox_lock_class_error_handling(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox lock class connection error."""

    await setup_integration(hass, entry)

    with (
        patch.object(mock_wallbox, "lockCharger", side_effect=http_404_error),
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
        patch.object(mock_wallbox, "lockCharger", side_effect=http_404_error),
        patch.object(mock_wallbox, "unlockCharger", side_effect=http_404_error),
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
        patch.object(mock_wallbox, "lockCharger", side_effect=http_404_error),
        patch.object(mock_wallbox, "unlockCharger", side_effect=http_404_error),
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
        patch.object(mock_wallbox, "lockCharger", side_effect=http_403_error),
        patch.object(mock_wallbox, "unlockCharger", side_effect=http_403_error),
        pytest.raises(InsufficientRights),
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
        patch.object(mock_wallbox, "lockCharger", side_effect=http_429_error),
        patch.object(mock_wallbox, "unlockCharger", side_effect=http_429_error),
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
