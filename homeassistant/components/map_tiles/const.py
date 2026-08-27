"""Constants for the Map tiles integration."""

from collections import deque
from datetime import timedelta
import re
from typing import Final

from aiohttp import ClientTimeout

from homeassistant.const import __version__
from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "map_tiles"
DATA_ACCESS_TOKENS: HassKey[deque[str]] = HassKey(DOMAIN)

VECTOR_URL: Final = "https://vector.openstreetmap.org"
RASTER_URL: Final = "https://tile.openstreetmap.org"
TILEJSON_URL: Final = f"{VECTOR_URL}/shortbread_v1/tilejson.json"
UPSTREAM_TIMEOUT: Final = ClientTimeout(total=10)

CONTACT: Final = "abuse@home-assistant.io"
UPSTREAM_HEADERS: Final = {
    # The raster endpoint blocks a browser that sends no `Referer` and accepts
    # an application `User-Agent` instead, which a browser cannot set.
    "User-Agent": (
        f"HomeAssistant/{__version__} (+https://www.home-assistant.io; {CONTACT})"
    ),
    # Pinned so the encoding that lands in the cache is one we can hand on; the
    # client session otherwise offers whichever codecs happen to be installed.
    "Accept-Encoding": "gzip",
}

# Refresh intervals, not lifetimes: an expired entry is never dropped, because
# it is what keeps the map up while upstream is unreachable.
TILE_TTL: Final = 24 * 60 * 60
# Glyphs and sprites are pinned to an upstream release and never change.
ASSET_TTL: Final = 30 * 24 * 60 * 60
# Short, because this is where a move of the tile source arrives.
TILEJSON_TTL: Final = 60 * 60

# The OSMF asks consumers to hold tiles for at least a week, which a browser can
# do for itself where this instance would spend memory doing it for them.
TILE_MAX_AGE: Final = 7 * 24 * 60 * 60
ASSET_MAX_AGE: Final = 30 * 24 * 60 * 60
TILEJSON_MAX_AGE: Final = 5 * 60

# A server side cache is needed because the access token rotates, which changes
# every URL and empties every browser cache with it. In memory rather than on
# disk: Home Assistant runs on SD cards, and losing the working set on restart
# costs a few dozen requests.
CACHE_MAX_BYTES: Final = 32 * 1024 * 1024

# Being blocked arrives as HTTP 200 with a valid PNG reading "Access blocked".
# Length is the cheap check, the digest confirms it.
BLOCKED_TILE_BYTES: Final = 6987
BLOCKED_TILE_SHA256: Final = (
    "b02c44252dac5a5e820ecef1e9bf9200e9407c042df668a466a1aa81a9ecca7a"
)

# MapLibre overzooms above the source maxzoom, so nothing legitimate asks for a
# vector tile past z14.
VECTOR_MAX_ZOOM: Final = 14
RASTER_MAX_ZOOM: Final = 19

# OSM's own TileJSON omits "contributors", which their guidelines ask for.
ATTRIBUTION: Final = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    " contributors"
)

FONTSTACK_RE: Final = re.compile(
    r"^[A-Za-z0-9 _-]{1,64}(?:,[A-Za-z0-9 _-]{1,64}){0,7}$"
)
GLYPH_RANGE_RE: Final = re.compile(r"^\d{1,5}-\d{1,5}\.pbf$")
SPRITE_SET_RE: Final = re.compile(r"^[a-z0-9_-]{1,32}$")
SPRITE_NAME_RE: Final = re.compile(r"^sprites(?:@2x)?$")

# Two tokens are live at a time, so one stays valid for 30 to 60 minutes.
TOKEN_CHANGE_INTERVAL: Final = timedelta(minutes=30)
