"""The tests for the LG webOS media player platform."""
from unittest.mock import patch

from homeassistant.components import media_player
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.webostv import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME
from homeassistant.setup import async_setup_component


async def test_select_source_with_empty_source_list(hass):
    """Test with dummy source."""
    with patch(
        "homeassistant.components.webostv.WebOsClient", spec=True,
    ):

        assert await async_setup_component(
            hass, media_player.DOMAIN, {media_player.DOMAIN: {}},
        )

        name = "fake"

        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_HOST: "fake", CONF_NAME: name}},
        )
        await hass.async_block_till_done()

        entity_id = f"{media_player.DOMAIN}.{name}"

        data = {
            ATTR_ENTITY_ID: entity_id,
            ATTR_INPUT_SOURCE: "nonexistent",
        }
        await hass.services.async_call(media_player.DOMAIN, SERVICE_SELECT_SOURCE, data)

        assert hass.states.is_state(entity_id, "playing")
