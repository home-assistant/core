"""Tests for the KEBA charging station display notifications.

The display is a legacy notify platform loaded by discovery without a name,
so its action is notify.notify, not notify.keba.
"""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import POLL_INTERVAL, FakeKebaStation, async_seconds_until_poll


@pytest.mark.parametrize(
    ("data", "command"),
    [
        ({"message": "Charging"}, "display 1 2 10 0 Charging"),
        ({"message": "Hello World"}, "display 1 2 10 0 Hello$World"),
        (
            {"message": "Done", "data": {"min_time": 5, "max_time": 30}},
            "display 1 5 30 0 Done",
        ),
        (
            {"message": "A message longer than the display"},
            "display 1 2 10 0 A$message$longer$than$t",
        ),
    ],
)
async def test_notify_shows_text(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    freezer: FrozenDateTimeFactory,
    data: dict[str, Any],
    command: str,
) -> None:
    """Test the display action sends text, with spaces as '$', cut to 23 characters."""
    await hass.services.async_call(NOTIFY_DOMAIN, "notify", data, blocking=True)
    await hass.async_block_till_done()

    assert setup_keba.commands[1:] == [command]
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == POLL_INTERVAL


async def test_display_action_is_named_notify(
    hass: HomeAssistant, setup_keba: FakeKebaStation
) -> None:
    """Test the display action is registered as notify.notify."""
    assert hass.services.has_service(NOTIFY_DOMAIN, "notify")
    assert not hass.services.has_service(NOTIFY_DOMAIN, "keba")
