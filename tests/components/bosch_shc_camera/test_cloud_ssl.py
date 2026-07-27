"""Tests for cloud_ssl.py's hass.data-cached SSL context helper."""

import asyncio
import ssl

from homeassistant.components.bosch_shc_camera.cloud_ssl import (
    _SSL_CONTEXT_DATA_KEY,
    async_get_bosch_cloud_ssl_context,
)
from homeassistant.core import HomeAssistant


async def test_ssl_context_is_cached_on_hass_data(hass: HomeAssistant) -> None:
    """A second call returns the exact same SSLContext instance (no rebuild)."""
    first = await async_get_bosch_cloud_ssl_context(hass)
    second = await async_get_bosch_cloud_ssl_context(hass)
    assert first is second
    assert isinstance(first, ssl.SSLContext)
    assert hass.data[_SSL_CONTEXT_DATA_KEY] is first


async def test_ssl_context_concurrent_callers_build_only_once(
    hass: HomeAssistant,
) -> None:
    """Concurrent first-callers race the lock but only build the context once."""
    results = await asyncio.gather(
        *[async_get_bosch_cloud_ssl_context(hass) for _ in range(5)]
    )
    assert len({id(r) for r in results}) == 1
