"""Tests for the syslog notification platform."""

import syslog
from unittest.mock import patch

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    ("facility", "expected_facility"),
    [
        ("auth", syslog.LOG_AUTH),
        ("kernel", syslog.LOG_KERN),
        ("local0", syslog.LOG_LOCAL0),
    ],
)
async def test_facility(
    hass: HomeAssistant, facility: str, expected_facility: int
) -> None:
    """Test that the configured facility is passed to syslog."""
    assert await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {"platform": "syslog", "name": "syslog", "facility": facility}
            ]
        },
    )
    await hass.async_block_till_done()

    with (
        patch("homeassistant.components.syslog.notify.syslog.openlog") as mock_openlog,
        patch("homeassistant.components.syslog.notify.syslog.syslog") as mock_syslog,
        patch("homeassistant.components.syslog.notify.syslog.closelog"),
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN, "syslog", {"message": "Hello"}, blocking=True
        )

    mock_openlog.assert_called_once_with(
        "Home Assistant", syslog.LOG_PID, expected_facility
    )
    mock_syslog.assert_called_once_with(syslog.LOG_INFO, "Hello")
