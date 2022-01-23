"""Tests for the WebOS TV integration."""
from unittest.mock import patch

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.webostv.const import DOMAIN
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TV_NAME = "fake"
ENTITY_ID = f"{MP_DOMAIN}.{TV_NAME}"
MOCK_CLIENT_KEYS = {"1.2.3.4": "some-secret"}

CHANNEL_1 = {
    "channelNumber": "1",
    "channelName": "Channel 1",
    "channelId": "ch1id",
}
CHANNEL_2 = {
    "channelNumber": "20",
    "channelName": "Channel Name 2",
    "channelId": "ch2id",
}


async def setup_webostv(hass, unique_id="some-unique-id"):
    """Initialize webostv and media_player for tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_CLIENT_SECRET: "0123456789",
        },
        title=TV_NAME,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.webostv.read_client_keys",
        return_value=MOCK_CLIENT_KEYS,
    ):
        await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {CONF_HOST: "1.2.3.4"}},
        )
        await hass.async_block_till_done()

    return entry
