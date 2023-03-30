"""The tests for an update of the Twitch component."""
from unittest.mock import MagicMock, patch

from homeassistant.components import sensor
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_ID = "sensor.channel123"
CONFIG = {
    sensor.DOMAIN: {
        "platform": "twitch",
        CONF_CLIENT_ID: "1234",
        CONF_CLIENT_SECRET: " abcd",
        "channels": ["channel123"],
    }
}
CONFIG_WITH_OAUTH = {
    sensor.DOMAIN: {
        "platform": "twitch",
        CONF_CLIENT_ID: "1234",
        CONF_CLIENT_SECRET: "abcd",
        "channels": ["channel123"],
        "token": "9876",
    }
}

USER_OBJECT = {
    "id": 123,
    "display_name": "channel123",
    "offline_image_url": "logo.png",
    "profile_image_url": "logo.png",
    "view_count": 42,
}
STREAM_OBJECT_ONLINE = {
    "game_name": "Good Game",
    "title": "Title",
    "thumbnail_url": "stream-medium.png",
}

FOLLOWERS_OBJECT = [{"followed_at": "2020-01-20T21:22:42"}] * 24
OAUTH_USER_ID = {"id": 987}
SUB_ACTIVE = {"is_gift": False}
FOLLOW_ACTIVE = {"followed_at": "2020-01-20T21:22:42"}


def make_data(data):
    """Create a data object."""
    return {"data": data, "total": len(data)}


async def test_init(hass: HomeAssistant) -> None:
    """Test initial config."""

    twitch_mock = MagicMock()
    twitch_mock.get_streams.return_value = make_data([])
    twitch_mock.get_users.return_value = make_data([USER_OBJECT])
    twitch_mock.get_users_follows.return_value = make_data(FOLLOWERS_OBJECT)
    twitch_mock.has_required_auth.return_value = False

    with patch(
        "homeassistant.components.twitch.sensor.Twitch", return_value=twitch_mock
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "offline"
    assert sensor_state.name == "channel123"
    assert sensor_state.attributes["icon"] == "mdi:twitch"
    assert sensor_state.attributes["friendly_name"] == "channel123"
    assert sensor_state.attributes["views"] == 42
    assert sensor_state.attributes["followers"] == 24


async def test_offline(hass: HomeAssistant) -> None:
    """Test offline state."""

    twitch_mock = MagicMock()
    twitch_mock.get_streams.return_value = make_data([])
    twitch_mock.get_users.return_value = make_data([USER_OBJECT])
    twitch_mock.get_users_follows.return_value = make_data(FOLLOWERS_OBJECT)
    twitch_mock.has_required_auth.return_value = False

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=twitch_mock,
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "offline"
    assert sensor_state.attributes["entity_picture"] == "logo.png"


async def test_streaming(hass: HomeAssistant) -> None:
    """Test streaming state."""

    twitch_mock = MagicMock()
    twitch_mock.get_users.return_value = make_data([USER_OBJECT])
    twitch_mock.get_users_follows.return_value = make_data(FOLLOWERS_OBJECT)
    twitch_mock.get_streams.return_value = make_data([STREAM_OBJECT_ONLINE])
    twitch_mock.has_required_auth.return_value = False

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=twitch_mock,
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "streaming"
    assert sensor_state.attributes["entity_picture"] == "stream-medium.png"
    assert sensor_state.attributes["game"] == "Good Game"
    assert sensor_state.attributes["title"] == "Title"


async def test_oauth_without_sub_and_follow(hass: HomeAssistant) -> None:
    """Test state with oauth."""

    twitch_mock = MagicMock()
    twitch_mock.get_streams.return_value = make_data([])
    twitch_mock.get_users.side_effect = [
        make_data([USER_OBJECT]),
        make_data([USER_OBJECT]),
        make_data([OAUTH_USER_ID]),
    ]
    twitch_mock.get_users_follows.side_effect = [
        make_data(FOLLOWERS_OBJECT),
        make_data([]),
    ]
    twitch_mock.has_required_auth.return_value = True
    twitch_mock.check_user_subscription.return_value = {"status": 404}

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=twitch_mock,
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_sub(hass: HomeAssistant) -> None:
    """Test state with oauth and sub."""

    twitch_mock = MagicMock()
    twitch_mock.get_streams.return_value = make_data([])
    twitch_mock.get_users.side_effect = [
        make_data([USER_OBJECT]),
        make_data([USER_OBJECT]),
        make_data([OAUTH_USER_ID]),
    ]
    twitch_mock.get_users_follows.side_effect = [
        make_data(FOLLOWERS_OBJECT),
        make_data([]),
    ]
    twitch_mock.has_required_auth.return_value = True

    # This function does not return an array so use make_data
    twitch_mock.check_user_subscription.return_value = make_data([SUB_ACTIVE])

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=twitch_mock,
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is True
    assert sensor_state.attributes["subscription_is_gifted"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_follow(hass: HomeAssistant) -> None:
    """Test state with oauth and follow."""

    twitch_mock = MagicMock()
    twitch_mock.get_streams.return_value = make_data([])
    twitch_mock.get_users.side_effect = [
        make_data([USER_OBJECT]),
        make_data([USER_OBJECT]),
        make_data([OAUTH_USER_ID]),
    ]
    twitch_mock.get_users_follows.side_effect = [
        make_data(FOLLOWERS_OBJECT),
        make_data([FOLLOW_ACTIVE]),
    ]
    twitch_mock.has_required_auth.return_value = True
    twitch_mock.check_user_subscription.return_value = {"status": 404}

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=twitch_mock,
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert sensor_state.attributes["following"] is True
    assert sensor_state.attributes["following_since"] == "2020-01-20T21:22:42"
