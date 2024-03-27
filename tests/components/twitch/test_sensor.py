"""The tests for an update of the Twitch component."""

from datetime import datetime
from unittest.mock import AsyncMock

from twitchAPI.object.api import FollowedChannel, Stream, UserSubscription
from twitchAPI.type import TwitchResourceNotFound

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.twitch.const import CONF_CHANNELS, DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from ...common import MockConfigEntry, load_json_object_fixture
from . import TwitchIterObject, get_generator_from_data, setup_integration

ENTITY_ID = "sensor.channel123"
CONFIG = {
    "auth_implementation": "cred",
    CONF_CLIENT_ID: "1234",
    CONF_CLIENT_SECRET: "abcd",
}

LEGACY_CONFIG_WITHOUT_TOKEN = {
    SENSOR_DOMAIN: {
        "platform": "twitch",
        CONF_CLIENT_ID: "1234",
        CONF_CLIENT_SECRET: "abcd",
        "channels": ["channel123"],
    }
}

LEGACY_CONFIG = {
    SENSOR_DOMAIN: {
        "platform": "twitch",
        CONF_CLIENT_ID: "1234",
        CONF_CLIENT_SECRET: "abcd",
        CONF_TOKEN: "efgh",
        "channels": ["channel123"],
    }
}

OPTIONS = {CONF_CHANNELS: ["channel123"]}


async def test_legacy_migration(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
    issue_registry: ir.IssueRegistry,
    mock_setup_entry,
) -> None:
    """Test importing legacy yaml."""
    assert await async_setup_component(hass, Platform.SENSOR, LEGACY_CONFIG)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert len(issue_registry.issues) == 1


async def test_legacy_migration_without_token(
    hass: HomeAssistant, twitch_mock: AsyncMock
) -> None:
    """Test importing legacy yaml."""
    assert await async_setup_component(
        hass, Platform.SENSOR, LEGACY_CONFIG_WITHOUT_TOKEN
    )
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0
    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == 1


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
