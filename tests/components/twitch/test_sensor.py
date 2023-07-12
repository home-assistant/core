"""The tests for an update of the Twitch component."""
from unittest.mock import patch

from homeassistant.components import sensor
from homeassistant.components.twitch.const import CONF_CHANNELS, DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import (
    TwitchAPIExceptionMock,
    TwitchInvalidTokenMock,
    TwitchInvalidUserMock,
    TwitchMissingScopeMock,
    TwitchMock,
    TwitchUnauthorizedMock,
)
from .conftest import ComponentSetup

ENTITY_ID = "sensor.channel123"
CONFIG = {
    "auth_implementation": "cred",
    CONF_CLIENT_ID: "1234",
    CONF_CLIENT_SECRET: "abcd",
}

LEGACY_CONFIG = {
    sensor.DOMAIN: {
        "platform": "twitch",
        CONF_CLIENT_ID: "1234",
        CONF_CLIENT_SECRET: "abcd",
        "channels": ["channel123"],
    }
}

OPTIONS = {CONF_CHANNELS: ["channel123"]}


async def test_legacy_migration(hass: HomeAssistant) -> None:
    """Test importing legacy yaml."""
    with patch(
        "homeassistant.components.twitch.sensor.Twitch", return_value=TwitchMock()
    ):
        assert await async_setup_component(hass, Platform.SENSOR, LEGACY_CONFIG)
        await hass.async_block_till_done()
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 0
        issue_registry = ir.async_get(hass)
        assert len(issue_registry.issues) == 1


async def test_init(hass: HomeAssistant, setup_integration: ComponentSetup) -> None:
    """Test initial config."""
    await setup_integration()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state


async def test_offline(hass: HomeAssistant, setup_integration: ComponentSetup) -> None:
    """Test offline state."""
    await setup_integration(TwitchMock(is_streaming=False))

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "offline"
    assert sensor_state.attributes["entity_picture"] == "logo.png"


async def test_streaming(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test streaming state."""
    await setup_integration()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "streaming"
    assert sensor_state.attributes["entity_picture"] == "stream-medium.png"
    assert sensor_state.attributes["game"] == "Good game"
    assert sensor_state.attributes["title"] == "Title"


async def test_oauth_without_sub_and_follow(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test state with oauth."""
    await setup_integration(TwitchMock(is_following=False))

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_sub(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test state with oauth and sub."""
    await setup_integration(
        TwitchMock(is_subscribed=True, is_gifted=False, is_following=False)
    )

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is True
    assert sensor_state.attributes["subscription_is_gifted"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_follow(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test state with oauth and follow."""
    await setup_integration()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["following"] is True
    assert sensor_state.attributes["following_since"] == "2020-01-20T21:22:42"


async def test_auth_with_invalid_credentials(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test auth with invalid credentials."""
    await setup_integration(TwitchUnauthorizedMock())

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state is None


async def test_auth_with_missing_scope(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test auth with invalid credentials."""
    await setup_integration(TwitchMissingScopeMock())

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state is None


async def test_auth_with_invalid_token(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test auth with invalid credentials."""
    await setup_integration(TwitchInvalidTokenMock())

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state is None


async def test_auth_with_invalid_user(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test auth with invalid user."""
    await setup_integration(TwitchInvalidUserMock())

    sensor_state = hass.states.get(ENTITY_ID)
    assert "subscribed" not in sensor_state.attributes


async def test_auth_with_api_exception(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test auth with invalid user."""
    await setup_integration(TwitchAPIExceptionMock())

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert "subscription_is_gifted" not in sensor_state.attributes
