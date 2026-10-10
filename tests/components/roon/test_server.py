"""Test the roon server."""

from homeassistant.components.roon.const import DOMAIN
from homeassistant.components.roon.server import RoonServer
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "media_player.kitchen"
RENAMED_ENTITY_ID = "media_player.renamed_kitchen"
ROON_NAME = "Kitchen"


def _server(hass: HomeAssistant) -> RoonServer:
    """Return a server with one registered player."""
    server = RoonServer(hass, MockConfigEntry(domain=DOMAIN))
    server.add_player_id(ENTITY_ID, ROON_NAME)
    return server


async def test_player_id_follows_rename(hass: HomeAssistant) -> None:
    """Test re-registering a renamed player maps its roon name to the new id."""
    server = _server(hass)

    server.remove_player_id(ENTITY_ID)
    server.add_player_id(RENAMED_ENTITY_ID, ROON_NAME)

    assert server.entity_id(ROON_NAME) == RENAMED_ENTITY_ID
    assert server.roon_name(RENAMED_ENTITY_ID) == ROON_NAME
    assert server.roon_name(ENTITY_ID) is None


async def test_remove_player_id(hass: HomeAssistant) -> None:
    """Test unregistering a player removes both mappings."""
    server = _server(hass)

    server.remove_player_id(ENTITY_ID)

    assert server.entity_id(ROON_NAME) is None
    assert server.roon_name(ENTITY_ID) is None


async def test_remove_stale_player_id_keeps_current(hass: HomeAssistant) -> None:
    """Test removing a stale id keeps the name mapped to the current id."""
    server = _server(hass)
    server.add_player_id(RENAMED_ENTITY_ID, ROON_NAME)

    server.remove_player_id(ENTITY_ID)

    assert server.entity_id(ROON_NAME) == RENAMED_ENTITY_ID
    assert server.roon_name(RENAMED_ENTITY_ID) == ROON_NAME
    assert server.roon_name(ENTITY_ID) is None
