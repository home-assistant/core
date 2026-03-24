"""Tests for Green Planet Energy services."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.components.green_planet_energy.services import (
    ATTR_HOURS,
    SERVICE_GET_PRICES,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

# Freeze at 2026-03-24 14:07:00 UTC — local slot boundary will be 14:00.
FROZEN_NOW = datetime(2026, 3, 24, 14, 7, 0, tzinfo=UTC)


async def _call_get_prices(hass: HomeAssistant, hours: float) -> dict:
    """Helper: call the get_prices service and return the response."""
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRICES,
        {ATTR_HOURS: hours},
        blocking=True,
        return_response=True,
    )


@pytest.fixture
def frozen_now():
    """Patch dt_util.now to a stable, known time."""
    with patch(
        "homeassistant.components.green_planet_energy.services.dt_util.now",
        return_value=FROZEN_NOW,
    ):
        yield FROZEN_NOW


async def test_get_prices_basic(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: datetime,
) -> None:
    """Requesting 1 hour returns exactly 4 contiguous 15-minute slots."""
    result = await _call_get_prices(hass, 1)

    prices = result["prices"]
    assert result["hours_requested"] == 1.0
    assert len(prices) == 4

    # Slots must be contiguous.
    for i in range(len(prices) - 1):
        assert prices[i]["end"] == prices[i + 1]["start"]

    # Each slot must have a positive price.
    for slot in prices:
        assert slot["price"] > 0
        assert "start" in slot
        assert "end" in slot


async def test_get_prices_slot_start_snapped(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: datetime,
) -> None:
    """Slot start is snapped to the current 15-minute boundary (14:00, not 14:07)."""
    result = await _call_get_prices(hass, 0.25)

    prices = result["prices"]
    assert len(prices) == 1
    # The first slot must start at 14:00 (the snapped boundary of 14:07).
    assert prices[0]["start"].startswith("2026-03-24T14:00:00")
    assert prices[0]["end"].startswith("2026-03-24T14:15:00")


async def test_get_prices_correct_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: datetime,
) -> None:
    """Prices match mock data formula: (20.0 + hour + minute/100) / 100 EUR/kWh."""
    result = await _call_get_prices(hass, 1)
    prices = result["prices"]

    # Slots: 14:00, 14:15, 14:30, 14:45 — all today (gpe_price_HH_MM keys).
    expected = [
        (14, 0),
        (14, 15),
        (14, 30),
        (14, 45),
    ]
    for slot, (hour, minute) in zip(prices, expected, strict=True):
        expected_price = round((20.0 + hour + minute / 100) / 100, 6)
        assert slot["price"] == pytest.approx(expected_price)


async def test_get_prices_crosses_midnight(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Slots that cross midnight use _tomorrow keys."""
    # Freeze at 23:45 UTC so the window (1 h) crosses midnight.
    midnight_cross = datetime(2026, 3, 24, 23, 45, 0, tzinfo=UTC)
    with patch(
        "homeassistant.components.green_planet_energy.services.dt_util.now",
        return_value=midnight_cross,
    ):
        result = await _call_get_prices(hass, 1)

    prices = result["prices"]
    assert len(prices) == 4

    # First slot 23:45 today, last slot 00:30 tomorrow — should all have prices.
    assert "23:45:00" in prices[0]["start"]
    assert "00:30:00" in prices[-1]["start"]


async def test_get_prices_missing_slots_omitted(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: datetime,
) -> None:
    """Slots whose key is absent from coordinator data are silently omitted."""
    # Remove the 14:15 slot from coordinator data to simulate a gap in API data.
    coordinator = init_integration.runtime_data
    del coordinator.data["gpe_price_14_15"]

    result = await _call_get_prices(hass, 1)

    # Only 3 of the 4 expected slots (14:00, *14:15*, 14:30, 14:45) are present.
    assert len(result["prices"]) == 3
    starts = [s["start"] for s in result["prices"]]
    assert not any("14:15:00" in s for s in starts)


async def test_get_prices_no_config_entry(
    hass: HomeAssistant,
) -> None:
    """Service raises when no config entry is set up."""
    # Load the component so async_setup runs and registers the service.
    await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(HomeAssistantError, match="No matching integration"):
        await _call_get_prices(hass, 1)


async def test_get_prices_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Service raises when the config entry exists but is not loaded."""
    # Load the component so the service is registered.
    await async_setup_component(hass, DOMAIN, {})
    # Add the config entry but do NOT call async_setup_entry — state stays NEVER_LOADED.
    mock_config_entry.add_to_hass(hass)
    with pytest.raises(HomeAssistantError, match="not currently loaded"):
        await _call_get_prices(hass, 1)


async def test_get_prices_quarter_hour(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: datetime,
) -> None:
    """Requesting 0.25 h (minimum) returns exactly 1 slot."""
    result = await _call_get_prices(hass, 0.25)
    assert len(result["prices"]) == 1
    assert result["hours_requested"] == 0.25


async def test_get_prices_non_quarter_hour_rejected(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: datetime,
) -> None:
    """Non-0.25-multiple hour values are rejected by the service schema."""
    with pytest.raises(HomeAssistantError):
        await _call_get_prices(hass, 0.3)
async def test_get_prices_max_hours(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Requesting 24 h from midnight returns up to 96 slots for that day."""
    midnight = datetime(2026, 3, 24, 0, 0, 0, tzinfo=UTC)
    with patch(
        "homeassistant.components.green_planet_energy.services.dt_util.now",
        return_value=midnight,
    ):
        result = await _call_get_prices(hass, 24)

    # 24 h * 4 slots/h = 96 slots, all today (mock provides 96 15-min keys/day).
    assert result["hours_requested"] == 24.0
    assert len(result["prices"]) == 96
