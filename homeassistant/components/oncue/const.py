"""Constants for the Oncue integration."""

import asyncio

import aiohttp

DOMAIN = "oncue"

CONNECTION_EXCEPTIONS = (asyncio.TimeoutError, aiohttp.ClientError)

CONNECTION_ESTABLISHED_KEY: str = "NetworkConnectionEstablished"

VALUE_UNAVAILABLE: str = "--"
