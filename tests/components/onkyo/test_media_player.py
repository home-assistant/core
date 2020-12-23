"""The tests for the Onkyo media player platform."""
import pytest

from homeassistant.components import media_player
from homeassistant.components.media_player.const import ATTR_MEDIA_VOLUME_MUTED
from homeassistant.components.onkyo.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    SERVICE_VOLUME_MUTE,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, patch

NAME = "my_receiver"
ENTITY_ID = f"{media_player.DOMAIN}.{NAME}"


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.onkyo.onkyo_rcv", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.host = "1.2.3.4"
        client.identifier = "0123456789"
        client.info = {"identifier": "0123456789", "model_name": "1A2B3C4"}
        client.model_name = "1A2B3C4"
        yield client


async def setup_platform(hass):
    """Initialize Onkyo and media_player for tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_NAME: "my_receiver"},
        unique_id="0123456789",
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: "1.2.3.4", CONF_NAME: "my_receiver"}},
    )
    await hass.async_block_till_done()


async def test_mute(hass, client):
    """Test simple service call."""
    await setup_platform(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_MEDIA_VOLUME_MUTED: True,
    }
    await hass.services.async_call(media_player.DOMAIN, SERVICE_VOLUME_MUTE, data)
    await hass.async_block_till_done()
    client.command.assert_any_call("audio-muting on")


async def test_turn_on(hass, client):
    """Test that turn on service calls function."""
    await setup_platform(hass)

    data = {ATTR_ENTITY_ID: ENTITY_ID}
    await hass.services.async_call(media_player.DOMAIN, "turn_on", data)
    await hass.async_block_till_done()
    client.command.assert_any_call("system-power on")
