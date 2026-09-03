"""Tests for the Famn notify platform."""

import re
from unittest.mock import AsyncMock

from famn_sdk import ApiError
import pytest

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .conftest import SPACE_ID

from tests.common import MockConfigEntry

ENTITY_ID = "notify.home_assistant_family"

pytestmark = [pytest.mark.usefixtures("mock_famn")]


async def test_send_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_space_api: AsyncMock,
) -> None:
    """Test sending a notification to the family."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MESSAGE: "Vannlekkasje på badet!",
            ATTR_TITLE: "Alarm",
        },
        blocking=True,
    )

    call = mock_space_api.notify_space_endpoint.call_args
    assert call.args[0] == SPACE_ID
    assert call.kwargs["body"].title == "Alarm"
    assert call.kwargs["body"].message == "Vannlekkasje på badet!"


async def test_send_message_to_member(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_space_api: AsyncMock,
) -> None:
    """Test notifying a single family member via their own entity."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: "notify.home_assistant_emma",
            ATTR_MESSAGE: "Middagen er klar!",
        },
        blocking=True,
    )

    call = mock_space_api.notify_space_endpoint.call_args
    assert call.args[0] == SPACE_ID
    assert call.kwargs["body"].account_id == "2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e"
    assert call.kwargs["body"].message == "Middagen er klar!"


async def test_member_without_account_gets_no_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that local members without an account get no notify entity."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("notify.home_assistant_jonas") is not None
    assert hass.states.get("notify.home_assistant_bestemor") is None


async def test_send_message_default_title(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_space_api: AsyncMock,
) -> None:
    """Test that a message without a title is attributed to Home Assistant."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MESSAGE: "Døren er åpen"},
        blocking=True,
    )

    call = mock_space_api.notify_space_endpoint.call_args
    assert call.kwargs["body"].title == "Home Assistant"


async def test_send_message_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_space_api: AsyncMock,
) -> None:
    """Test that a Famn error surfaces as a Home Assistant error."""
    await setup_integration(hass, mock_config_entry)
    mock_space_api.notify_space_endpoint.side_effect = ApiError(429, "rate limited")

    with pytest.raises(
        HomeAssistantError, match=re.escape("Failed to notify the family via Famn")
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MESSAGE: "Test"},
            blocking=True,
        )
