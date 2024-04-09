"""The tests for an update of the Twitch component."""

from datetime import datetime

import pytest

from homeassistant.core import HomeAssistant

from ...common import MockConfigEntry
from . import (
    TwitchAPIExceptionMock,
    TwitchInvalidTokenMock,
    TwitchInvalidUserMock,
    TwitchMissingScopeMock,
    TwitchMock,
    TwitchUnauthorizedMock,
    setup_integration,
)

ENTITY_ID = "sensor.channel123"


async def test_offline(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test offline state."""
    twitch.is_streaming = False
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "offline"
    assert sensor_state.attributes["entity_picture"] == "logo.png"


async def test_streaming(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test streaming state."""
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "streaming"
    assert sensor_state.attributes["entity_picture"] == "stream-medium.png"
    assert sensor_state.attributes["game"] == "Good game"
    assert sensor_state.attributes["title"] == "Title"


async def test_oauth_without_sub_and_follow(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test state with oauth."""
    twitch.is_following = False
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_sub(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test state with oauth and sub."""
    twitch.is_subscribed = True
    twitch.is_following = False
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is True
    assert sensor_state.attributes["subscription_is_gifted"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_follow(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test state with oauth and follow."""
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["following"] is True
    assert sensor_state.attributes["following_since"] == datetime(
        year=2023, month=8, day=1
    )


@pytest.mark.parametrize(
    "twitch_mock",
    [TwitchUnauthorizedMock(), TwitchMissingScopeMock(), TwitchInvalidTokenMock()],
)
async def test_auth_invalid(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test auth failures."""
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state is None


@pytest.mark.parametrize("twitch_mock", [TwitchInvalidUserMock()])
async def test_auth_with_invalid_user(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test auth with invalid user."""
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert "subscribed" not in sensor_state.attributes


@pytest.mark.parametrize("twitch_mock", [TwitchAPIExceptionMock()])
async def test_auth_with_api_exception(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test auth with invalid user."""
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert "subscription_is_gifted" not in sensor_state.attributes
