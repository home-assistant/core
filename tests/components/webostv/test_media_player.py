"""The tests for the LG webOS media player platform."""
from unittest.mock import patch

import pytest

from homeassistant.components import media_player
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_MUTED,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.webostv.const import (
    ATTR_BUTTON,
    ATTR_PAYLOAD,
    DOMAIN,
    SERVICE_BUTTON,
    SERVICE_COMMAND,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_ICON,
    CONF_NAME,
    SERVICE_VOLUME_MUTE,
)

from tests.common import MockConfigEntry

NAME = "fake"
ENTITY_ID = f"{media_player.DOMAIN}.{NAME}"


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.webostv.WebOsClient", autospec=True
    ) as mock_client_class:
        mock_client_class.create.return_value = mock_client_class.return_value
        client = mock_client_class.return_value
        client.software_info = {"device_id": "00:01:02:03:04"}
        client.client_key = "0123456789"
        client.apps = {0: {"title": "Applicaiton01"}}
        client.inputs = {0: {"label": "Input01"}}
        yield client


async def setup_webostv(hass):
    """Initialize webostv and media_player for tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_NAME: NAME,
            "client_secret": "0123456789",
            CONF_ICON: "mdi:test",
        },
        unique_id="00:01:02:03:04",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_mute(hass, client):
    """Test simple service call."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_MEDIA_VOLUME_MUTED: True,
    }

    assert await hass.services.async_call(
        media_player.DOMAIN, SERVICE_VOLUME_MUTE, data, True
    )
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
    """Test generic command functionality."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test",
    }
    await hass.services.async_call(DOMAIN, SERVICE_COMMAND, data)
    await hass.async_block_till_done()

    client.request.assert_called_with("test", payload=None)


async def test_command_with_optional_arg(hass, client):
    """Test generic command functionality."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test",
        ATTR_PAYLOAD: {"target": "https://www.google.com"},
    }
    await hass.services.async_call(DOMAIN, SERVICE_COMMAND, data)
    await hass.async_block_till_done()

    client.request.assert_called_with(
        "test", payload={"target": "https://www.google.com"}
    )
