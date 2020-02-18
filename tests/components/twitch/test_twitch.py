"""The tests for an update of the Twitch component."""
from unittest.mock import MagicMock, patch

from requests import HTTPError
from twitch.resources import Channel, Follow, Stream, Subscription, User

from homeassistant.components import sensor
from homeassistant.setup import async_setup_component

ENTITY_ID = "sensor.channel123"
CONFIG = {
    sensor.DOMAIN: {
        "platform": "twitch",
        "client_id": "1234",
        "channels": ["channel123"],
    }
}
CONFIG_WITH_OAUTH = {
    sensor.DOMAIN: {
        "platform": "twitch",
        "client_id": "1234",
        "channels": ["channel123"],
        "token": "9876",
    }
}

USER_ID = User({"id": 123, "display_name": "channel123", "logo": "logo.png"})
STREAM_OBJECT_ONLINE = Stream(
    {
        "channel": {"game": "Good Game", "status": "Title"},
        "preview": {"medium": "stream-medium.png"},
    }
)
CHANNEL_OBJECT = Channel({"followers": 42, "views": 24})
OAUTH_USER_ID = User({"id": 987})
SUB_ACTIVE = Subscription({"created_at": "2020-01-20T21:22:42", "is_gift": False})
FOLLOW_ACTIVE = Follow({"created_at": "2020-01-20T21:22:42"})


async def test_init(hass):
    """Test initial config."""

    channels = MagicMock()
    channels.get_by_id.return_value = CHANNEL_OBJECT
    streams = MagicMock()
    streams.get_stream_by_user.return_value = None

    twitch_mock = MagicMock()
    twitch_mock.users.translate_usernames_to_ids.return_value = [USER_ID]
    twitch_mock.channels = channels
    twitch_mock.streams = streams

    with patch(
        "homeassistant.components.twitch.sensor.TwitchClient", return_value=twitch_mock
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "offline"
    assert sensor_state.name == "channel123"
    assert sensor_state.attributes["icon"] == "mdi:twitch"
    assert sensor_state.attributes["friendly_name"] == "channel123"
    assert sensor_state.attributes["views"] == 24
    assert sensor_state.attributes["followers"] == 42


async def test_offline(hass):
    """Test offline state."""

    twitch_mock = MagicMock()
    twitch_mock.users.translate_usernames_to_ids.return_value = [USER_ID]
    twitch_mock.channels.get_by_id.return_value = CHANNEL_OBJECT
    twitch_mock.streams.get_stream_by_user.return_value = None

    with patch(
        "homeassistant.components.twitch.sensor.TwitchClient", return_value=twitch_mock,
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "offline"
    assert sensor_state.attributes["entity_picture"] == "logo.png"


async def test_streaming(hass):
    """Test streaming state."""

    twitch_mock = MagicMock()
    twitch_mock.users.translate_usernames_to_ids.return_value = [USER_ID]
    twitch_mock.channels.get_by_id.return_value = CHANNEL_OBJECT
    twitch_mock.streams.get_stream_by_user.return_value = STREAM_OBJECT_ONLINE

    with patch(
        "homeassistant.components.twitch.sensor.TwitchClient", return_value=twitch_mock,
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "streaming"
    assert sensor_state.attributes["entity_picture"] == "stream-medium.png"
    assert sensor_state.attributes["game"] == "Good Game"
    assert sensor_state.attributes["title"] == "Title"


async def test_oauth_without_sub_and_follow(hass):
    """Test state with oauth."""

    twitch_mock = MagicMock()
    twitch_mock.users.translate_usernames_to_ids.return_value = [USER_ID]
    twitch_mock.channels.get_by_id.return_value = CHANNEL_OBJECT
    twitch_mock._oauth_token = True  # A replacement for the token
    twitch_mock.users.get.return_value = OAUTH_USER_ID
    twitch_mock.users.check_subscribed_to_channel.side_effect = HTTPError()
    twitch_mock.users.check_follows_channel.side_effect = HTTPError()

    with patch(
        "homeassistant.components.twitch.sensor.TwitchClient", return_value=twitch_mock,
    ):
        assert (
            await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH) is True
        )

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_sub(hass):
    """Test state with oauth and sub."""

    twitch_mock = MagicMock()
    twitch_mock.users.translate_usernames_to_ids.return_value = [USER_ID]
    twitch_mock.channels.get_by_id.return_value = CHANNEL_OBJECT
    twitch_mock._oauth_token = True  # A replacement for the token
    twitch_mock.users.get.return_value = OAUTH_USER_ID
    twitch_mock.users.check_subscribed_to_channel.return_value = SUB_ACTIVE
    twitch_mock.users.check_follows_channel.side_effect = HTTPError()

    with patch(
        "homeassistant.components.twitch.sensor.TwitchClient", return_value=twitch_mock,
    ):
        assert (
            await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH) is True
        )

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is True
    assert sensor_state.attributes["subscribed_since"] == "2020-01-20T21:22:42"
    assert sensor_state.attributes["subscription_is_gifted"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_follow(hass):
    """Test state with oauth and follow."""

    twitch_mock = MagicMock()
    twitch_mock.users.translate_usernames_to_ids.return_value = [USER_ID]
    twitch_mock.channels.get_by_id.return_value = CHANNEL_OBJECT
    twitch_mock._oauth_token = True  # A replacement for the token
    twitch_mock.users.get.return_value = OAUTH_USER_ID
    twitch_mock.users.check_subscribed_to_channel.side_effect = HTTPError()
    twitch_mock.users.check_follows_channel.return_value = FOLLOW_ACTIVE

    with patch(
        "homeassistant.components.twitch.sensor.TwitchClient", return_value=twitch_mock,
    ):
        assert (
            await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH) is True
        )

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert sensor_state.attributes["following"] is True
    assert sensor_state.attributes["following_since"] == "2020-01-20T21:22:42"
