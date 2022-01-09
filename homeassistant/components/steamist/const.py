"""Constants for the Steamist integration."""

import asyncio

import aiohttp

DOMAIN = "steamist"

CONNECTION_EXCEPTIONS = (asyncio.TimeoutError, aiohttp.ClientError)
