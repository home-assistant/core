"""Test the Prowl notifications."""

import logging

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import API_BASE_URL

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.asyncio
async def test_send_notification(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    configure_prowl_through_yaml,
) -> None:
    """Test sending a notification message via Prowl."""
    # Mock up a successful call to the Prowl API.
    aioclient_mock.post(f"{API_BASE_URL}add", text="success", status=200)

    test_message = {"message": "Test Notification", "data": {"url": "http://localhost"}}
    await hass.services.async_call(
        NOTIFY_DOMAIN, NOTIFY_DOMAIN, test_message, blocking=True
    )

    # Confirm we successfully tried to call the Prowl API.
    assert aioclient_mock.call_count > 0


@pytest.mark.asyncio
async def test_fail_send_notification(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    configure_prowl_through_yaml,
) -> None:
    """Test sending a notification message via Prowl."""
    # Mock up a failed call to the Prowl API.
    aioclient_mock.post(f"{API_BASE_URL}add", text="error", status=500)

    test_message = {"message": "Test Notification"}

    with caplog.at_level(logging.ERROR):
        await hass.services.async_call(
            NOTIFY_DOMAIN, NOTIFY_DOMAIN, test_message, blocking=True
        )

        # Ensure we called the Prowl API.
        assert aioclient_mock.call_count > 0

        # Ensure the Prowl component logged an error.
        assert "Prowl service returned http status 500" in caplog.text


@pytest.mark.asyncio
async def test_timeout_send_notification(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    configure_prowl_through_yaml,
) -> None:
    """Test sending a notification message via Prowl."""
    # Mock up a failed call to the Prowl API.
    aioclient_mock.post(f"{API_BASE_URL}add", exc=TimeoutError())

    test_message = {"message": "Test Notification"}

    with caplog.at_level(logging.ERROR):
        await hass.services.async_call(
            NOTIFY_DOMAIN, NOTIFY_DOMAIN, test_message, blocking=True
        )

        # Ensure the Prowl component logged an error.
        assert "Timeout accessing Prowl at" in caplog.text
