"""Constants for the Oncue integration."""

import aiohttp
from aiooncue import ServiceFailedException

DOMAIN = "oncue"

CONNECTION_EXCEPTIONS = (
    TimeoutError,
    aiohttp.ClientError,
    ServiceFailedException,
)

CONNECTION_ESTABLISHED_KEY: str = "NetworkConnectionEstablished"

VALUE_UNAVAILABLE: str = "--"
