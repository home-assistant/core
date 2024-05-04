"""Constants for the Steamist integration."""

import aiohttp

DOMAIN = "steamist"

CONNECTION_EXCEPTIONS = (TimeoutError, aiohttp.ClientError)

STARTUP_SCAN_TIMEOUT = 5
DISCOVER_SCAN_TIMEOUT = 10

DISCOVERY = "discovery"
