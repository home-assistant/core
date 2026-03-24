"""Constants for the Brands integration."""

from __future__ import annotations

from datetime import timedelta
import re
from typing import Final

from aiohttp import ClientTimeout

DOMAIN: Final = "brands"

# CDN
BRANDS_CDN_URL: Final = "https://brands.home-assistant.io"
CDN_TIMEOUT: Final = ClientTimeout(total=10)
PLACEHOLDER: Final = "_placeholder"

# Caching
CACHE_TTL: Final = 30 * 24 * 60 * 60  # 30 days in seconds

# Access token
TOKEN_CHANGE_INTERVAL: Final = timedelta(minutes=30)

# Validation
CATEGORY_RE: Final = re.compile(r"^[a-z0-9_]+$")
HARDWARE_IMAGE_RE: Final = re.compile(r"^[a-z0-9_-]+\.png$")

# Images and fallback chains
ALLOWED_IMAGES: Final = frozenset(
    {
        "icon.png",
        "logo.png",
        "icon@2x.png",
        "logo@2x.png",
        "dark_icon.png",
        "dark_logo.png",
        "dark_icon@2x.png",
        "dark_logo@2x.png",
    }
)

# Fallback chains for image resolution, mirroring the brands CDN build logic.
# When a requested image is not found, we try each fallback in order.
IMAGE_FALLBACKS: Final[dict[str, list[str]]] = {
    "logo.png": ["icon.png"],
    "icon@2x.png": ["icon.png"],
    "logo@2x.png": ["logo.png", "icon.png"],
    "dark_icon.png": ["icon.png"],
    "dark_logo.png": ["dark_icon.png", "logo.png", "icon.png"],
    "dark_icon@2x.png": ["icon@2x.png", "icon.png"],
    "dark_logo@2x.png": [
        "dark_icon@2x.png",
        "logo@2x.png",
        "logo.png",
        "icon.png",
    ],
}
