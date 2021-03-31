"""Helper for httpx."""
import sys
from typing import Any, Callable, Optional

import httpx

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE, __version__
from homeassistant.core import Event, callback
from homeassistant.helpers.frame import warn_use
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass

DATA_ASYNC_CLIENT = "httpx_async_client"
DATA_ASYNC_CLIENT_NOVERIFY = "httpx_async_client_noverify"
SERVER_SOFTWARE = "HomeAssistant/{0} httpx/{1} Python/{2[0]}.{2[1]}".format(
    __version__, httpx.__version__, sys.version_info
)
USER_AGENT = "User-Agent"


@callback
@bind_hass
def get_async_client(
    hass: HomeAssistantType, verify_ssl: bool = True
) -> httpx.AsyncClient:
    """Return default httpx AsyncClient.

    This method must be run in the event loop.
    """
    key = DATA_ASYNC_CLIENT if verify_ssl else DATA_ASYNC_CLIENT_NOVERIFY

    client: Optional[httpx.AsyncClient] = hass.data.get(key)

    if client is None:
        client = hass.data[key] = create_async_httpx_client(hass, verify_ssl)

    return client


@callback
def create_async_httpx_client(
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
