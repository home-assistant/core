"""The tests for an update of the Twitch component."""

from datetime import datetime
from unittest.mock import AsyncMock

from twitchAPI.object.api import FollowedChannel, Stream, UserSubscription
from twitchAPI.type import TwitchResourceNotFound

from homeassistant.components.twitch import DOMAIN
from homeassistant.core import HomeAssistant

from . import TwitchIterObject, get_generator_from_data, setup_integration

from tests.common import MockConfigEntry, load_json_object_fixture

ENTITY_ID = "sensor.channel123"


async def test_offline(
    hass: HomeAssistant, twitch_mock: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Test offline state."""
    twitch_mock.return_value.get_streams.return_value = get_generator_from_data(
        [], Stream
    )
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "offline"
    assert sensor_state.attributes["entity_picture"] == "logo.png"


async def test_streaming(
    hass: HomeAssistant, twitch_mock: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Test streaming state."""
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "streaming"
    assert sensor_state.attributes["entity_picture"] == "stream-medium.png"
    assert sensor_state.attributes["game"] == "Good game"
    assert sensor_state.attributes["title"] == "Title"


async def test_oauth_without_sub_and_follow(
    hass: HomeAssistant, twitch_mock: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Test state with oauth."""
    twitch_mock.return_value.get_followed_channels.return_value = TwitchIterObject(
        "empty_response.json", FollowedChannel
    )
    twitch_mock.return_value.check_user_subscription.side_effect = (
        TwitchResourceNotFound
    )
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_sub(
    hass: HomeAssistant, twitch_mock: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Test state with oauth and sub."""
    twitch_mock.return_value.get_followed_channels.return_value = TwitchIterObject(
        "empty_response.json", FollowedChannel
    )
    twitch_mock.return_value.check_user_subscription.return_value = UserSubscription(
        **load_json_object_fixture("check_user_subscription_2.json", DOMAIN)
    )
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is True
    assert sensor_state.attributes["subscription_is_gifted"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_follow(
    hass: HomeAssistant, twitch_mock: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Test state with oauth and follow."""
    await setup_integration(hass, config_entry)

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["following"] is True
    assert sensor_state.attributes["following_since"] == datetime(
        year=2023, month=8, day=1
    )
