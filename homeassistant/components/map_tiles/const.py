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
    # OSM blocks referer-less browser requests; the accepted alternative is an
    # identifying application `User-Agent`, which this proxy supplies because
    # a browser cannot.
    "User-Agent": (
        f"HomeAssistant/{__version__} (+https://www.home-assistant.io; {CONTACT})"
    ),
    # Pinned to gzip so cached bodies are in an encoding every client accepts;
    # the session default advertises whichever codecs happen to be installed.
    "Accept-Encoding": "gzip",
}

# Fallback refresh intervals, used only when upstream sends no Cache-Control
# max-age to honor. Intervals, not lifetimes: an expired entry is never dropped,
# because it is what keeps the map up while upstream is unreachable.
TILE_TTL: Final = 7 * 24 * 60 * 60
# Glyphs and sprites are pinned to an upstream release and never change.
ASSET_TTL: Final = 30 * 24 * 60 * 60
# Short: the TileJSON is how upstream would announce a moved tile endpoint.
TILEJSON_TTL: Final = 60 * 60

# The OSMF asks consumers to cache tiles for at least a week; the max-age
# delegates that to the browser cache instead of this instance's memory.
TILE_MAX_AGE: Final = 7 * 24 * 60 * 60
ASSET_MAX_AGE: Final = 30 * 24 * 60 * 60
TILEJSON_MAX_AGE: Final = 5 * 60

# A server side cache is needed because the access token rotates, which changes
# every URL and empties every browser cache with it. In memory rather than on
# disk: Home Assistant runs on SD cards, and losing the working set on restart
# costs a few dozen requests.
CACHE_MAX_BYTES: Final = 32 * 1024 * 1024

# Far above any legitimate asset (tiles top out at a few hundred KB), so only a
# hostile or broken upstream hits them; they bound what a single response can
# make this process hold in memory, on the wire and after decompression.
MAX_FETCH_BYTES: Final = 8 * 1024 * 1024
MAX_DECOMPRESSED_BYTES: Final = 32 * 1024 * 1024

# Bounds both in-flight body memory (this many concurrent fetches, each capped
# at MAX_FETCH_BYTES) and how many parallel requests reach the volunteer-run OSM
# servers at once.
MAX_CONCURRENT_FETCHES: Final = 16

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

# Bytes of entropy per access token.
TOKEN_SIZE: Final = 32

# Two tokens are live at a time, so one stays valid for 30 to 60 minutes.
TOKEN_CHANGE_INTERVAL: Final = timedelta(minutes=30)
