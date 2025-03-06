"""Nice G.O. switch tests."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from nice_go import ApiError, AuthFailedError
import pytest

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry


async def test_turn_on(
    hass: HomeAssistant, mock_nice_go: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn on switch."""
    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_garage_1_vacation_mode"},
        blocking=True,
    )
    mock_nice_go.vacation_mode_on.assert_called_once_with("1")


async def test_turn_off(
    hass: HomeAssistant, mock_nice_go: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn off switch."""
    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_garage_2_vacation_mode"},
        blocking=True,
    )
    mock_nice_go.vacation_mode_off.assert_called_once_with("2")


@pytest.mark.parametrize(
    ("action", "error", "entity_id", "expected_error"),
    [
        (
            SERVICE_TURN_OFF,
            ApiError,
            "switch.test_garage_1_vacation_mode",
            "Error while turning off the switch",
        ),
        (
            SERVICE_TURN_ON,
            ClientError,
            "switch.test_garage_2_vacation_mode",
            "Error while turning on the switch",
        ),
    ],
)
async def test_error(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    error: Exception,
    entity_id: str,
    expected_error: str,
) -> None:
    """Test that errors are handled appropriately."""

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    mock_nice_go.vacation_mode_on.side_effect = error
    mock_nice_go.vacation_mode_off.side_effect = error

    with pytest.raises(HomeAssistantError, match=expected_error):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            action,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_auth_failed_error(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that if an auth failed error occurs, the integration attempts a token refresh and a retry before throwing an error."""

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    def _on_side_effect(*args, **kwargs):
        if mock_nice_go.vacation_mode_on.call_count <= 3:
            raise AuthFailedError
        if mock_nice_go.vacation_mode_on.call_count == 5:
            raise AuthFailedError
        if mock_nice_go.vacation_mode_on.call_count == 6:
            raise ApiError

    def _off_side_effect(*args, **kwargs):
        if mock_nice_go.vacation_mode_off.call_count <= 3:
            raise AuthFailedError
        if mock_nice_go.vacation_mode_off.call_count == 4:
            raise ApiError

    mock_nice_go.vacation_mode_on.side_effect = _on_side_effect
    mock_nice_go.vacation_mode_off.side_effect = _off_side_effect

    with pytest.raises(HomeAssistantError, match="Error while turning on the switch"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_garage_1_vacation_mode"},
            blocking=True,
        )

    assert mock_nice_go.authenticate.call_count == 1
    assert mock_nice_go.vacation_mode_on.call_count == 2

    with pytest.raises(HomeAssistantError, match="Error while turning off the switch"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test_garage_2_vacation_mode"},
            blocking=True,
        )

    assert mock_nice_go.authenticate.call_count == 2
    assert mock_nice_go.vacation_mode_off.call_count == 2

    # Try again, but this time the auth failed error should not be raised

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_garage_1_vacation_mode"},
        blocking=True,
    )

    assert mock_nice_go.authenticate.call_count == 3
    assert mock_nice_go.vacation_mode_on.call_count == 4

    # One more time but with an ApiError instead of AuthFailed

    with pytest.raises(HomeAssistantError, match="Error while turning on the switch"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_garage_1_vacation_mode"},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError, match="Error while turning off the switch"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test_garage_2_vacation_mode"},
            blocking=True,
        )

    assert mock_nice_go.authenticate.call_count == 5
    assert mock_nice_go.vacation_mode_on.call_count == 6
    assert mock_nice_go.vacation_mode_off.call_count == 4
