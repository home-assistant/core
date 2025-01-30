"""Test the Prowl notifications."""

import logging
from unittest.mock import patch

import pytest

from homeassistant.components.prowl.notify import ProwlNotificationService
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_load_yaml_config(
    hass: HomeAssistant, configure_prowl_through_yaml: None
) -> None:
    """Test sending a notification message via Prowl."""
    yield


@pytest.mark.asyncio
async def test_send_notification(hass: HomeAssistant) -> None:
    """Test sending a notification message via Prowl."""
    prowl = ProwlNotificationService(hass, "f00f" * 10)

    with patch.object(prowl, "_prowl"):
        await prowl.async_send_message(
            "Test Notification", data={"url": "http://localhost"}
        )


@pytest.mark.asyncio
async def test_fail_send_notification(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending a notification message via Prowl."""
    prowl = ProwlNotificationService(hass, "f00f" * 10)
    with (
        patch.object(
            prowl._prowl,
            "notify",
            side_effect=Exception("Prowl service returned http status 500"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        await prowl.async_send_message(
            "Test Notification", data={"url": "http://localhost"}
        )

        # Ensure the Prowl component logged an error.
        assert "Prowl service returned http status 500" in caplog.text


@pytest.mark.asyncio
async def test_timeout_send_notification(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending a notification message via Prowl."""
    prowl = ProwlNotificationService(hass, "f00f" * 10)
    with (
        patch.object(prowl._prowl, "notify", side_effect=TimeoutError),
        caplog.at_level(logging.ERROR),
    ):
        await prowl.async_send_message(
            "Test Notification", data={"url": "http://localhost"}
        )

        # Ensure the Prowl component logged an error.
        assert "Timeout accessing Prowl at" in caplog.text
