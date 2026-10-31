"""Tests for the KEBA charging station display notifications.

The display is a legacy notify platform loaded by discovery without a name,
so its action is notify.notify, not notify.keba.
"""

from typing import Any
from unittest.mock import MagicMock, call

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import POLL_INTERVAL, async_seconds_until_poll


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"message": "Charging"}, call("Charging", 2.0, 10.0)),
        ({"message": "Hello World"}, call("Hello$World", 2.0, 10.0)),
        (
            {"message": "Done", "data": {"min_time": 5, "max_time": 30}},
            call("Done", 5.0, 30.0),
        ),
        # Cut to the display's 23 characters by the library, not here.
        (
            {"message": "A message longer than the display"},
            call("A$message$longer$than$the$display", 2.0, 10.0),
        ),
    ],
)
async def test_notify_shows_text(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    freezer: FrozenDateTimeFactory,
    data: dict[str, Any],
    expected: Any,
) -> None:
    """Test the display action passes the text with spaces as '$', without fast polling."""
    await hass.services.async_call(NOTIFY_DOMAIN, "notify", data, blocking=True)
    await hass.async_block_till_done()

    assert setup_keba.set_text.await_args_list == [expected]
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == POLL_INTERVAL


async def test_display_action_is_named_notify(
    hass: HomeAssistant, setup_keba: MagicMock
) -> None:
    """Test the display action is registered as notify.notify."""
    assert hass.services.has_service(NOTIFY_DOMAIN, "notify")
    assert not hass.services.has_service(NOTIFY_DOMAIN, "keba")
