"""Cloud util functions."""

import os

from hass_nabucasa import Cloud

from homeassistant.components import http
from homeassistant.core import HomeAssistant
from homeassistant.helpers.singleton import singleton

from .client import CloudClient
from .const import DOMAIN

_STRICT_CONNECTION_GUARD_PAGE_NAME = "strict_connection_guard_page.html"
_STRICT_CONNECTION_GUARD_PAGE = os.path.join(
    os.path.dirname(__file__), _STRICT_CONNECTION_GUARD_PAGE_NAME
)


def get_strict_connection_mode(hass: HomeAssistant) -> http.const.StrictConnectionMode:
    """Get the strict connection mode."""
    cloud: Cloud[CloudClient] = hass.data[DOMAIN]
    return cloud.client.prefs.strict_connection


@singleton(f"{DOMAIN}_{_STRICT_CONNECTION_GUARD_PAGE_NAME}")
async def read_strict_connection_guard_page(hass: HomeAssistant) -> str:
    """Read the strict connection guard page from disk via executor."""

    def read_guard_page() -> str:
        with open(_STRICT_CONNECTION_GUARD_PAGE, encoding="utf-8") as file:
            return file.read()

    return await hass.async_add_executor_job(read_guard_page)
