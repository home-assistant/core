"""Tests for the Kodi integration."""
from unittest.mock import patch

from .conftest import PATCH_KODI_CONNMAN


async def stop_integration(hass):
    """Teardown without error by unregistering the callbacks.

    This is only needed when initializing the integration with websockets.
    """
    with patch(
        f"{PATCH_KODI_CONNMAN}.unregister_websocket_callback", return_value=True
    ):
        await hass.async_stop()
