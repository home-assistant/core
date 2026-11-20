"""Test the ONVIF camera platform."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.camera import async_get_stream_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import PASSWORD, USERNAME, setup_onvif_integration

ENTITY_ID = "camera.testcamera_profile1"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_stream_uri_retried_after_failure(hass: HomeAssistant) -> None:
    """Test the stream URI is fetched again after a failed attempt."""
    _, _, device = await setup_onvif_integration(hass)
    device.username = USERNAME
    device.password = PASSWORD
    device.async_get_stream_uri = AsyncMock(
        side_effect=[TimeoutError, "rtsp://1.2.3.4/stream"]
    )

    with pytest.raises(TimeoutError):
        await async_get_stream_source(hass, ENTITY_ID)

    assert (
        await async_get_stream_source(hass, ENTITY_ID)
        == f"rtsp://{USERNAME}:{PASSWORD}@1.2.3.4/stream"
    )
    assert device.async_get_stream_uri.await_count == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_stream_uri_request_cancelled(hass: HomeAssistant) -> None:
    """Test a cancelled request neither blocks waiting calls nor later ones."""
    _, _, device = await setup_onvif_integration(hass)
    device.username = USERNAME
    device.password = PASSWORD
    request_started = asyncio.Event()
    calls = 0

    async def get_stream_uri(profile: Any) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            request_started.set()
            await asyncio.Event().wait()
        return "rtsp://1.2.3.4/stream"

    device.async_get_stream_uri = get_stream_uri

    first = hass.async_create_task(async_get_stream_source(hass, ENTITY_ID))
    await request_started.wait()
    waiting = hass.async_create_task(async_get_stream_source(hass, ENTITY_ID))
    await asyncio.sleep(0)

    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    # The waiting call gets an error instead of waiting forever
    async with asyncio.timeout(5):
        with pytest.raises(HomeAssistantError, match="cancelled"):
            await waiting

    assert (
        await async_get_stream_source(hass, ENTITY_ID)
        == f"rtsp://{USERNAME}:{PASSWORD}@1.2.3.4/stream"
    )
    assert calls == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_stream_uri_waiting_call_cancelled(hass: HomeAssistant) -> None:
    """Test a cancelled waiting call neither cancels the request nor others."""
    _, _, device = await setup_onvif_integration(hass)
    device.username = USERNAME
    device.password = PASSWORD
    request_started = asyncio.Event()
    answer = asyncio.Event()
    calls = 0

    async def get_stream_uri(profile: Any) -> str:
        nonlocal calls
        calls += 1
        request_started.set()
        await answer.wait()
        return "rtsp://1.2.3.4/stream"

    device.async_get_stream_uri = get_stream_uri

    first = hass.async_create_task(async_get_stream_source(hass, ENTITY_ID))
    await request_started.wait()
    cancelled = hass.async_create_task(async_get_stream_source(hass, ENTITY_ID))
    waiting = hass.async_create_task(async_get_stream_source(hass, ENTITY_ID))
    await asyncio.sleep(0)

    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    answer.set()
    uri = f"rtsp://{USERNAME}:{PASSWORD}@1.2.3.4/stream"
    async with asyncio.timeout(5):
        assert await first == uri
        assert await waiting == uri
    assert calls == 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_stream_uri_waiting_call_and_request_cancelled(
    hass: HomeAssistant,
) -> None:
    """Test cancelling a waiting call and then the request itself."""
    _, _, device = await setup_onvif_integration(hass)
    device.username = USERNAME
    device.password = PASSWORD
    request_started = asyncio.Event()
    calls = 0

    async def get_stream_uri(profile: Any) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            request_started.set()
            await asyncio.Event().wait()
        return "rtsp://1.2.3.4/stream"

    device.async_get_stream_uri = get_stream_uri

    first = hass.async_create_task(async_get_stream_source(hass, ENTITY_ID))
    await request_started.wait()
    cancelled = hass.async_create_task(async_get_stream_source(hass, ENTITY_ID))
    await asyncio.sleep(0)

    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    # The next call asks the camera again
    async with asyncio.timeout(5):
        assert (
            await async_get_stream_source(hass, ENTITY_ID)
            == f"rtsp://{USERNAME}:{PASSWORD}@1.2.3.4/stream"
        )
    assert calls == 2
