"""Constants for the Oncue integration."""

import asyncio

import aiohttp
from aiooncue import ServiceFailedException

DOMAIN = "oncue"

CONNECTION_EXCEPTIONS = (
    asyncio.TimeoutError,
    aiohttp.ClientError,
    ServiceFailedException,
)

CONNECTION_ESTABLISHED_KEY: str = "NetworkConnectionEstablished"

VALUE_UNAVAILABLE: str = "--"
