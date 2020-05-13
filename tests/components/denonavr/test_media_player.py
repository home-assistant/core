"""The tests for the denonavr media player platform."""
import pytest

from homeassistant.components import media_player
from homeassistant.components.denonavr import ATTR_COMMAND, DOMAIN, SERVICE_GET_COMMAND
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PLATFORM
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

NAME = "fake"
ENTITY_ID = f"{media_player.DOMAIN}.{NAME}"


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.denonavr.media_player.denonavr.DenonAVR",
        autospec=True,
    ) as mock_client_class, patch(
        "homeassistant.components.denonavr.media_player.denonavr.discover"
    ):
        mock_client_class.return_value.name = NAME
        mock_client_class.return_value.zones = {"Main": mock_client_class.return_value}
        yield mock_client_class.return_value


async def setup_denonavr(hass):
    """Initialize webostv and media_player for tests."""
    assert await async_setup_component(
        hass,
        media_player.DOMAIN,
        {
            media_player.DOMAIN: {
                CONF_PLATFORM: "denonavr",
                CONF_HOST: "fake",
                CONF_NAME: NAME,
            }
        },
    )
    await hass.async_block_till_done()


async def test_get_command(hass, client):
    """Test generic command functionality."""

    await setup_denonavr(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test",
    }
    await hass.services.async_call(DOMAIN, SERVICE_GET_COMMAND, data)
    await hass.async_block_till_done()

    client.send_get_command.assert_called_with("test")
