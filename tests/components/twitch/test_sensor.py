"""The tests for an update of the Twitch component."""
from unittest.mock import patch

import pytest

from homeassistant.components import sensor
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.twitch.const import CONF_CHANNELS, DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    TwitchAPIExceptionMock,
    TwitchInvalidTokenMock,
    TwitchInvalidUserMock,
    TwitchMissingScopeMock,
    TwitchMock,
    TwitchUnauthorizedMock,
)

from tests.common import MockConfigEntry

ENTITY_ID = "sensor.twitch_channel123"
CONFIG = {
    "auth_implementation": "cred",
    CONF_CLIENT_ID: "1234",
    CONF_CLIENT_SECRET: "abcd",
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
OPTIONS = {CONF_CHANNELS: ["channel123"]}


@pytest.fixture
async def component_setup(hass: HomeAssistant) -> None:
    """Fixture for setting up the integration."""
    assert await async_setup_component(hass, "application_credentials", {})

    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("client", "secret"), "cred"
    )


async def test_init(hass: HomeAssistant, component_setup, aioclient_mock) -> None:
    """Test initial config."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG, options=OPTIONS)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchMock(is_streaming=False),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state


async def test_offline(hass: HomeAssistant) -> None:
    """Test offline state."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchMock(is_streaming=False),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "offline"
    assert sensor_state.attributes["entity_picture"] == "logo.png"


async def test_streaming(hass: HomeAssistant) -> None:
    """Test streaming state."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchMock(),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.state == "streaming"
    assert sensor_state.attributes["entity_picture"] == "stream-medium.png"
    assert sensor_state.attributes["game"] == "Good game"
    assert sensor_state.attributes["title"] == "Title"


async def test_oauth_without_sub_and_follow(hass: HomeAssistant) -> None:
    """Test state with oauth."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchMock(is_following=False),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_sub(hass: HomeAssistant) -> None:
    """Test state with oauth and sub."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchMock(
            is_subscribed=True, is_gifted=False, is_following=False
        ),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is True
    assert sensor_state.attributes["subscription_is_gifted"] is False
    assert sensor_state.attributes["following"] is False


async def test_oauth_with_follow(hass: HomeAssistant) -> None:
    """Test state with oauth and follow."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchMock(),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["following"] is True
    assert sensor_state.attributes["following_since"] == "2020-01-20T21:22:42"


async def test_auth_with_invalid_credentials(hass: HomeAssistant) -> None:
    """Test auth with invalid credentials."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchUnauthorizedMock(),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state is None


async def test_auth_with_missing_scope(hass: HomeAssistant) -> None:
    """Test auth with invalid credentials."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchMissingScopeMock(),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state is None


async def test_auth_with_invalid_token(hass: HomeAssistant) -> None:
    """Test auth with invalid credentials."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchInvalidTokenMock(),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state is None


async def test_auth_with_invalid_user(hass: HomeAssistant) -> None:
    """Test auth with invalid user."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchInvalidUserMock(),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert "subscribed" not in sensor_state.attributes


async def test_auth_with_api_exception(hass: HomeAssistant) -> None:
    """Test auth with invalid user."""

    with patch(
        "homeassistant.components.twitch.sensor.Twitch",
        return_value=TwitchAPIExceptionMock(),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG_WITH_OAUTH)
        await hass.async_block_till_done()

    sensor_state = hass.states.get(ENTITY_ID)
    assert sensor_state.attributes["subscribed"] is False
    assert "subscription_is_gifted" not in sensor_state.attributes
