"""The tests for the LG webOS media player platform."""
import sys

import pytest

from homeassistant.components import media_player
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_MUTED,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.webostv.const import (
    ATTR_BUTTON,
    ATTR_COMMAND,
    DOMAIN,
    SERVICE_BUTTON,
    SERVICE_COMMAND,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    SERVICE_VOLUME_MUTE,
)
from homeassistant.setup import async_setup_component

if sys.version_info >= (3, 8, 0):
    from unittest.mock import patch
else:
    from tests.async_mock import patch


NAME = "fake"
ENTITY_ID = f"{media_player.DOMAIN}.{NAME}"


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.webostv.WebOsClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.connection = True
        client.software_info = {"device_id": "a1:b1:c1:d1:e1:f1"}
        yield client


async def setup_webostv(hass):
    """Initialize webostv and media_player for tests."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_HOST: "fake", CONF_NAME: NAME}},
    )
    await hass.async_block_till_done()


async def test_mute(hass, client):
    """Test simple service call."""

    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_MEDIA_VOLUME_MUTED: True,
    }
    await hass.services.async_call(media_player.DOMAIN, SERVICE_VOLUME_MUTE, data)
    await hass.async_block_till_done()

    client.set_mute.assert_called_once()


async def test_select_source_with_empty_source_list(hass, client):
    """Ensure we don't call client methods when we don't have sources."""

    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_INPUT_SOURCE: "nonexistent",
    }
    await hass.services.async_call(media_player.DOMAIN, SERVICE_SELECT_SOURCE, data)
    await hass.async_block_till_done()

    client.launch_app.assert_not_called()
    client.set_input.assert_not_called()


async def test_button(hass, client):
    """Test generic button functionality."""

    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_BUTTON: "test",
    }
    await hass.services.async_call(DOMAIN, SERVICE_BUTTON, data)
    await hass.async_block_till_done()

    client.button.assert_called_once()
    client.button.assert_called_with("test")


async def test_command(hass, client):
    """Test generic button functionality."""

    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test",
    }
    await hass.services.async_call(DOMAIN, SERVICE_COMMAND, data)
    await hass.async_block_till_done()

    client.request.assert_called_with("test")
