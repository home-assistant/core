"""Helper for httpx."""
from functools import partial
import sys
from typing import Any, Callable, cast

import httpx

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE, __version__
from homeassistant.core import Event, callback
from homeassistant.helpers.frame import warn_use
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_callback_threadsafe

DATA_CLIENT = "httpx_client"
DATA_CLIENT_NOVERIFY = "httpx_client_noverify"
DATA_ASYNC_CLIENT = "httpx_async_client"
DATA_ASYNC_CLIENT_NOVERIFY = "httpx_async_client_noverify"
SERVER_SOFTWARE = "HomeAssistant/{0} httpx/{1} Python/{2[0]}.{2[1]}".format(
    __version__, httpx.__version__, sys.version_info
)
USER_AGENT = "User-Agent"


@callback
@bind_hass
def async_get_async_client(
    hass: HomeAssistantType, verify_ssl: bool = True
) -> httpx.AsyncClient:
    """Return default httpx AsyncClient.

    This method must be run in the event loop.
    """
    key = DATA_ASYNC_CLIENT if verify_ssl else DATA_ASYNC_CLIENT_NOVERIFY

    hass.data.setdefault(key, async_create_async_httpx_client(hass, verify_ssl))

    return cast(httpx.AsyncClient, hass.data[key])


@callback
@bind_hass
def async_get_client(hass: HomeAssistantType, verify_ssl: bool = True) -> httpx.Client:
    """Return default httpx Client.

    This method must be run in the event loop.
    """
    key = DATA_CLIENT if verify_ssl else DATA_CLIENT_NOVERIFY

    hass.data.setdefault(key, async_create_httpx_client(hass, verify_ssl))

    return cast(httpx.Client, hass.data[key])


@bind_hass
def get_client(hass: HomeAssistantType, verify_ssl: bool = True) -> httpx.Client:
    """Return default httpx Client."""
    return run_callback_threadsafe(
        hass.loop,
        partial(async_get_client, hass, verify_ssl=verify_ssl),
    ).result()


@callback
@bind_hass
def async_create_async_httpx_client(
    hass: HomeAssistantType,
    verify_ssl: bool = True,
    auto_cleanup: bool = True,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create a new httpx.AsyncClient with kwargs, i.e. for cookies.

    If auto_cleanup is False, the client will be
    automatically closed on homeassistant_stop.

    This method must be run in the event loop.
    """

    client = httpx.AsyncClient(
        verify=verify_ssl,
        headers={USER_AGENT: SERVER_SOFTWARE},
        **kwargs,
    )

    original_aclose = client.aclose

    client.aclose = warn_use(  # type: ignore
        client.aclose, "closes the Home Assistant httpx client"
    )

    if auto_cleanup:
        _async_register_async_client_shutdown(hass, client, original_aclose)

    return client


class HASShttpxClient(httpx.Client):
    """httpx client that cannot be accidentally closed."""

    original_close = httpx.Client.close

    def __del__(self) -> None:
        """Override __del__ to point to the original close function."""
        self.original_close()


@callback
@bind_hass
def async_create_httpx_client(
    hass: HomeAssistantType,
    verify_ssl: bool = True,
    auto_cleanup: bool = True,
    **kwargs: Any,
) -> httpx.Client:
    """Create a new httpx.Client with kwargs, i.e. for cookies.

    If auto_cleanup is False, the client will be
    automatically closed on homeassistant_stop.

    This method must be run in the event loop.
    """
    client = HASShttpxClient(
        verify=verify_ssl,
        headers={USER_AGENT: SERVER_SOFTWARE},
        **kwargs,
    )

    client.close = warn_use(  # type: ignore
        client.close, "closes the Home Assistant httpx client"
    )

    if auto_cleanup:
        _async_register_client_shutdown(hass, client, client.original_close)

    return client


@bind_hass
def create_httpx_client(
    hass: HomeAssistantType,
    verify_ssl: bool = True,
    auto_cleanup: bool = True,
    **kwargs: Any,
) -> httpx.Client:
    """Create a new httpx.Client with kwargs, i.e. for cookies.

    If auto_cleanup is False, the client will be
    automatically closed on homeassistant_stop.
    """
    return run_callback_threadsafe(
        hass.loop,
        partial(
            async_create_httpx_client,
            hass,
            verify_ssl=verify_ssl,
            auto_cleanup=auto_cleanup,
            **kwargs,
        ),
    ).result()


@callback
def _async_register_async_client_shutdown(
    hass: HomeAssistantType,
    client: httpx.AsyncClient,
    original_aclose: Callable[..., Any],
) -> None:
    """Register httpx AsyncClient aclose on Home Assistant shutdown.

    This method must be run in the event loop.
    """

    async def _async_close_client(event: Event) -> None:
        """Close httpx client."""
        await original_aclose()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_client)


@callback
def _async_register_client_shutdown(
    hass: HomeAssistantType, client: httpx.Client, original_close: Callable[..., Any]
) -> None:
    """Register httpx Client close on Home Assistant shutdown.

    This method must be run in the event loop.
    """

    def _close_client(event: Event) -> None:
        """Close httpx client."""
        original_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _close_client)
