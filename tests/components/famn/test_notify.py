"""Tests for the Famn notify platform."""

import re
from unittest.mock import AsyncMock

from famn_sdk import ApiError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.famn.coordinator import SCAN_INTERVAL
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
    NotifyEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .conftest import SPACE_ID

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "notify.home_assistant_family"
MEMBER_ENTITY_ID = "notify.home_assistant_emma"

pytestmark = [pytest.mark.usefixtures("mock_famn")]


async def test_title_capability_is_advertised(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that both notify entities report that they accept a title."""
    await setup_integration(hass, mock_config_entry)

    for entity_id in (ENTITY_ID, MEMBER_ENTITY_ID):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes[ATTR_SUPPORTED_FEATURES] & NotifyEntityFeature.TITLE, (
            f"{entity_id} forwards a title but does not advertise it"
        )


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


async def test_member_entity_unavailable_when_member_leaves(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_space_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a member's notify entity goes unavailable when they leave."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(MEMBER_ENTITY_ID).state == STATE_UNKNOWN

    # Emma leaves the space, so there is no phone left to push to.
    mock_space_api.get_space_members_endpoint.return_value = [
        member
        for member in mock_space_api.get_space_members_endpoint.return_value
        if member.display_name != "Emma"
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(MEMBER_ENTITY_ID).state == STATE_UNAVAILABLE
