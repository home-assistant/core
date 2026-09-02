"""The Map tiles integration.

Serves the frontend's base map - OpenStreetMap vector tiles, their TileJSON,
glyphs and sprites, and raster tiles for devices that cannot render vector ones.

A proxy is needed because the OSMF tile policy wants requests identified via
`User-Agent` or `Referer`, and a browser can send neither: both are forbidden
header names, and the default referrer (the page origin) would expose the
user's Nabu Casa installation URL.
"""

from collections import deque
from datetime import datetime
import secrets
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .cache import MapTilesCache
from .const import DATA_ACCESS_TOKENS, DOMAIN, TOKEN_CHANGE_INTERVAL, TOKEN_SIZE
from .views import (
    MapTilesGlyphsView,
    MapTilesRasterView,
    MapTilesSpriteIndexView,
    MapTilesSpriteSheetView,
    MapTilesTileJsonView,
    MapTilesVectorView,
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Map tiles integration."""
    # Leaflet asks for raster tiles with an <img>, which can carry no header, so
    # the token has to live in the URL.
    access_tokens: deque[str] = deque([secrets.token_hex(TOKEN_SIZE)], maxlen=2)
    hass.data[DATA_ACCESS_TOKENS] = access_tokens

    @callback
    def _rotate_token(_now: datetime) -> None:
        """Rotate the access token."""
        access_tokens.append(secrets.token_hex(TOKEN_SIZE))

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
