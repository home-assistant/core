"""Tests for Green Planet Energy services."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.components.green_planet_energy.services import (
    ATTR_HOURS,
    SERVICE_GET_PRICES,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
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
def frozen_now() -> Generator[None]:
    """Freeze time at FROZEN_NOW for service slot-snapping tests."""
    with patch(
        "homeassistant.components.green_planet_energy.services.dt_util.now",
        return_value=FROZEN_NOW,
    ):
        yield


async def test_get_prices_basic(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: None,
) -> None:
    """Requesting 1 hour returns exactly 4 contiguous 15-minute slots."""
    result = await _call_get_prices(hass, 1)

    prices = result["prices"]
    assert result["hours_requested"] == 1.0
    assert len(prices) == 4

    for i in range(len(prices) - 1):
        assert prices[i]["end"] == prices[i + 1]["start"]

    for slot in prices:
        assert slot["price"] > 0
        assert "start" in slot
        assert "end" in slot


async def test_get_prices_slot_start_snapped(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: None,
) -> None:
    """Slot start is snapped to the current 15-minute boundary (14:00, not 14:07)."""
    result = await _call_get_prices(hass, 0.25)

    prices = result["prices"]
    assert len(prices) == 1
    assert prices[0]["start"].startswith("2026-03-24T14:00:00")
    assert prices[0]["end"].startswith("2026-03-24T14:15:00")


async def test_get_prices_correct_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: None,
) -> None:
    """Prices match mock data formula: (20.0 + hour + minute/100) / 100 EUR/kWh."""
    result = await _call_get_prices(hass, 1)
    prices = result["prices"]

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

    assert "23:45:00" in prices[0]["start"]
    assert "00:30:00" in prices[-1]["start"]


async def test_get_prices_missing_slots_omitted(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: None,
) -> None:
    """Slots whose key is absent from coordinator data are silently omitted."""
    # Remove the 14:15 slot from coordinator data to simulate a gap in API data.
    coordinator = init_integration.runtime_data
    del coordinator.data["gpe_price_14_15"]

    result = await _call_get_prices(hass, 1)

    assert len(result["prices"]) == 3
    starts = [s["start"] for s in result["prices"]]
    assert not any("14:15:00" in s for s in starts)


async def test_get_prices_no_config_entry(
    hass: HomeAssistant,
) -> None:
    """Service raises when no config entry is set up."""
    await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_get_prices(hass, 1)
    assert exc_info.value.translation_key == "no_config_entry"


async def test_get_prices_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Service raises when the config entry exists but is not loaded."""
    await async_setup_component(hass, DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_get_prices(hass, 1)
    assert exc_info.value.translation_key == "config_entry_not_loaded"


async def test_get_prices_quarter_hour(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: None,
) -> None:
    """Requesting 0.25 h (minimum) returns exactly 1 slot."""
    result = await _call_get_prices(hass, 0.25)
    assert len(result["prices"]) == 1
    assert result["hours_requested"] == 0.25


async def test_get_prices_non_quarter_hour_rejected(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    frozen_now: None,
) -> None:
    """Non-0.25-multiple hour values are rejected by the service schema."""
    with pytest.raises(vol.Invalid):
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

    assert result["hours_requested"] == 24.0
    assert len(result["prices"]) == 96
