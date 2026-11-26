"""Tests for the KEBA charging station display notifications."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    NotifyService,
    NotifyServiceArgument,
)
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({NotifyServiceArgument.MESSAGE: "Charging"}, ("Charging", 2.0, 10.0)),
        ({NotifyServiceArgument.MESSAGE: "Hello World"}, ("Hello$World", 2.0, 10.0)),
        (
            {
                NotifyServiceArgument.MESSAGE: "Done",
                NotifyServiceArgument.DATA: {"min_time": 5, "max_time": 30},
            },
            ("Done", 5.0, 30.0),
        ),
    ],
)
async def test_notify(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    data: dict[str, Any],
    expected: tuple[str, float, float],
) -> None:
    """Test notify.notify shows the text on the display, with spaces as '$'."""
    await hass.services.async_call(
        NOTIFY_DOMAIN, NotifyService.NOTIFY, data, blocking=True
    )

    setup_keba.set_text.assert_awaited_once_with(*expected)
