"""Tests for the calendar/alternate_dates websocket command."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from homeassistant.components.calendar import DOMAIN
from homeassistant.components.calendar.alternate_calendar import (
    AlternateCalendarRegistry,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    CHINESE_CALENDAR_TYPE,
    HIJRI_CALENDAR_TYPE,
    MockChineseProvider,
    MockHijriProvider,
)

from tests.typing import WebSocketGenerator

PERSIAN_CALENDAR_TYPE = "persian"

type SendCommandFn = Callable[..., Awaitable[dict[str, Any]]]


@pytest.fixture(autouse=True)
async def setup_calendar(hass: HomeAssistant) -> None:
    """Set up the calendar component to register its websocket commands."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


@pytest.fixture(name="send_command")
async def send_command_fixture(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> SendCommandFn:
    """Return a callable sending an alternate_dates command."""

    async def _send(**payload: Any) -> dict[str, Any]:
        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "calendar/alternate_dates", **payload})
        return await client.receive_json()

    return _send


@pytest.mark.parametrize(
    ("start", "end", "expected_dates"),
    [
        ("2025-06-26", "2025-06-28", ["2025-06-26", "2025-06-27", "2025-06-28"]),
        ("2025-06-26", "2025-06-26", ["2025-06-26"]),
    ],
)
async def test_alternate_dates_range(
    send_command: SendCommandFn,
    registry: type[AlternateCalendarRegistry],
    start: str,
    end: str,
    expected_dates: list[str],
) -> None:
    """Test a range returns converted dates for every registered provider."""
    registry.register(HIJRI_CALENDAR_TYPE)(MockHijriProvider)
    registry.register(CHINESE_CALENDAR_TYPE)(MockChineseProvider)

    msg = await send_command(start=start, end=end)

    assert msg["success"]
    result = msg["result"]
    assert set(result) == set(expected_dates)
    for date_str in expected_dates:
        assert result[date_str] == [
            {
                "calendar_type": HIJRI_CALENDAR_TYPE,
                "calendar_name": "Hijri",
                "display_name": f"Hijri date for {date_str}",
                "date_str": date_str,
                "metadata": {"era": "AH"},
            },
            {
                "calendar_type": CHINESE_CALENDAR_TYPE,
                "calendar_name": "Chinese",
                "display_name": "Chinese date",
                "date_str": date_str,
                "metadata": {},
            },
        ]


async def test_alternate_dates_filters_calendar_types(
    send_command: SendCommandFn,
    registry: type[AlternateCalendarRegistry],
) -> None:
    """Test the calendar_types filter restricts which providers run."""
    registry.register(HIJRI_CALENDAR_TYPE)(MockHijriProvider)
    registry.register(CHINESE_CALENDAR_TYPE)(MockChineseProvider)

    msg = await send_command(
        start="2025-06-26",
        end="2025-06-27",
        calendar_types=[HIJRI_CALENDAR_TYPE],
    )

    assert msg["success"]
    for date_str, alternate_dates in msg["result"].items():
        assert [alternate["calendar_type"] for alternate in alternate_dates] == [
            HIJRI_CALENDAR_TYPE
        ]
        assert alternate_dates[0]["display_name"] == f"Hijri date for {date_str}"


async def test_alternate_dates_empty_range(
    send_command: SendCommandFn,
    registry: type[AlternateCalendarRegistry],
) -> None:
    """Test a range where start is after end returns no dates."""
    registry.register(HIJRI_CALENDAR_TYPE)(MockHijriProvider)

    msg = await send_command(start="2025-06-28", end="2025-06-26")

    assert msg["success"]
    assert msg["result"] == {}


async def test_alternate_dates_unknown_calendar_type(
    send_command: SendCommandFn,
    registry: type[AlternateCalendarRegistry],
) -> None:
    """Test requesting an unregistered calendar type returns a translated error."""
    registry.register(HIJRI_CALENDAR_TYPE)(MockHijriProvider)

    msg = await send_command(
        start="2025-06-26",
        end="2025-06-27",
        calendar_types=[PERSIAN_CALENDAR_TYPE],
    )

    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
    assert msg["error"]["translation_domain"] == DOMAIN
    assert msg["error"]["translation_key"] == "unknown_alternate_calendar"
    assert msg["error"]["translation_placeholders"] == {
        "calendar_type": PERSIAN_CALENDAR_TYPE
    }
