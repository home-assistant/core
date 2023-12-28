"""Test the Tessie cover platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import ERROR_UNKNOWN, TEST_RESPONSE, setup_platform


async def test_window(hass: HomeAssistant) -> None:
    """Tests that the window cover entity is correct."""

    await setup_platform(hass)

    entity_id = "cover.test_vent_windows"
    assert hass.states.get(entity_id).state == STATE_CLOSED

    # Test open windows
    with patch(
        "homeassistant.components.tessie.cover.vent_windows",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_set.assert_called_once()
    assert hass.states.get(entity_id).state == STATE_OPEN

    # Test close windows
    with patch(
        "homeassistant.components.tessie.cover.close_windows",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_set.assert_called_once()
    assert hass.states.get(entity_id).state == STATE_CLOSED


async def test_charge_port(hass: HomeAssistant) -> None:
    """Tests that the charge port cover entity is correct."""

    await setup_platform(hass)

    entity_id = "cover.test_charge_port_door"
    assert hass.states.get(entity_id).state == STATE_OPEN

    # Test close charge port
    with patch(
        "homeassistant.components.tessie.cover.close_charge_port",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_set.assert_called_once()
    assert hass.states.get(entity_id).state == STATE_CLOSED

    # Test open charge port
    with patch(
        "homeassistant.components.tessie.cover.open_unlock_charge_port",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_set.assert_called_once()
    assert hass.states.get(entity_id).state == STATE_OPEN


async def test_errors(hass: HomeAssistant) -> None:
    """Tests errors are handled."""

    await setup_platform(hass)
    entity_id = "cover.test_charge_port_door"

    # Test setting cover open with unknown error
    with patch(
        "homeassistant.components.tessie.cover.open_unlock_charge_port",
        side_effect=ERROR_UNKNOWN,
    ) as mock_set, pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_set.assert_called_once()
        assert error.from_exception == ERROR_UNKNOWN
