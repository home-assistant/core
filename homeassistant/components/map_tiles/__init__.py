"""The Map tiles integration.

Serves the frontend's base map - OpenStreetMap vector tiles, their TileJSON,
glyphs and sprites, and raster tiles for devices that cannot render vector ones.

It is a proxy because a browser cannot identify the application it belongs to:
`User-Agent` and `Referer` are forbidden header names, and the only referrer a
browser can send is its origin, which identifies a Nabu Casa installation.
"""

from collections import deque
from random import SystemRandom
from typing import Any, Final

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .cache import MapTilesCache
from .const import DATA_ACCESS_TOKENS, DOMAIN, TOKEN_CHANGE_INTERVAL
from .views import (
    MapTilesGlyphsView,
    MapTilesRasterView,
    MapTilesSpriteIndexView,
    MapTilesSpriteSheetView,
    MapTilesTileJsonView,
    MapTilesVectorView,
)

_RND: Final = SystemRandom()

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


def _new_token() -> str:
    """Return a fresh access token."""
    return hex(_RND.getrandbits(256))[2:]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Map tiles integration."""
    # Leaflet asks for raster tiles with an <img>, which can carry no header, so
    # the token has to live in the URL.
    access_tokens: deque[str] = deque([_new_token()], maxlen=2)
    hass.data[DATA_ACCESS_TOKENS] = access_tokens

    @callback
    def _rotate_token(_now: Any) -> None:
        """Rotate the access token."""
        access_tokens.append(_new_token())

    async_track_time_interval(
        hass, _rotate_token, TOKEN_CHANGE_INTERVAL, cancel_on_shutdown=True
    )

    cache = MapTilesCache(hass)
    for view in (
        MapTilesTileJsonView,
        MapTilesVectorView,
        MapTilesRasterView,
        MapTilesGlyphsView,
        MapTilesSpriteIndexView,
        MapTilesSpriteSheetView,
    ):
        hass.http.register_view(view(hass, cache))

    websocket_api.async_register_command(hass, ws_access_token)
    return True


@callback
@websocket_api.websocket_command({vol.Required("type"): "map_tiles/access_token"})
def ws_access_token(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the current map tiles access token."""
    connection.send_result(msg["id"], {"token": hass.data[DATA_ACCESS_TOKENS][-1]})
