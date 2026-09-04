"""Tests for Green Planet Energy services."""

from unittest.mock import MagicMock

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.components.green_planet_energy.services import (
    ATTR_HOURS,
    SERVICE_GET_PRICES,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def _call_get_prices(hass: HomeAssistant, hours: float, entry_id: str) -> dict:
    """Call get_prices and return the service response."""
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRICES,
        {ATTR_CONFIG_ENTRY_ID: entry_id, ATTR_HOURS: hours},
        blocking=True,
        return_response=True,
    )


async def _call_get_cheapest_duration(
    hass: HomeAssistant, duration: float, time_range: str | None = None
) -> dict:
    """Call get_cheapest_duration and return the service response."""
    data: dict[str, float | str] = {"duration": duration}
    if time_range is not None:
        data["time_range"] = time_range

    return await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        data,
        blocking=True,
        return_response=True,
    )


@pytest.mark.freeze_time("2026-03-24 14:07:00-07:00")
async def test_get_prices_basic(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Requesting 1 hour returns the expected response."""
    result = await _call_get_prices(hass, 1, init_integration.entry_id)

    assert result == snapshot


@pytest.mark.freeze_time("2026-03-24 14:07:00-07:00")
async def test_get_prices_slot_start_snapped(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Slot start is snapped to the current 15-minute boundary."""
    result = await _call_get_prices(hass, 0.25, init_integration.entry_id)

    prices = result["prices"]
    assert len(prices) == 1
    assert prices[0]["start"].startswith("2026-03-24T14:00:00")
    assert prices[0]["end"].startswith("2026-03-24T14:15:00")


@pytest.mark.freeze_time("2026-03-24 14:07:00-07:00")
async def test_get_prices_correct_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Prices match the expected 15-minute mock data values."""
    result = await _call_get_prices(hass, 1, init_integration.entry_id)
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


@pytest.mark.freeze_time("2026-03-24 23:45:00-07:00")
async def test_get_prices_crosses_midnight(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Slots that cross midnight use the expected response data."""
    result = await _call_get_prices(hass, 1, init_integration.entry_id)

    assert result == snapshot


@pytest.mark.freeze_time("2026-03-24 14:07:00-07:00")
async def test_get_prices_missing_slots_omitted(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Missing data keys are omitted from the returned slots."""
    coordinator = init_integration.runtime_data
    del coordinator.data["gpe_price_14_15"]

    result = await _call_get_prices(hass, 1, init_integration.entry_id)

    assert result == snapshot


async def test_get_prices_entry_not_found(hass: HomeAssistant) -> None:
    """Service raises when the config entry does not exist."""
    await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_get_prices(hass, 1, "non_existent_entry_id")
    assert exc_info.value.translation_key == "service_config_entry_not_found"


async def test_get_prices_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Service raises when the config entry exists but is not loaded."""
    await async_setup_component(hass, DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_get_prices(hass, 1, mock_config_entry.entry_id)
    assert exc_info.value.translation_key == "service_config_entry_not_loaded"


@pytest.mark.freeze_time("2026-03-24 14:07:00-07:00")
async def test_get_prices_quarter_hour(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Requesting 0.25 h returns exactly one slot."""
    result = await _call_get_prices(hass, 0.25, init_integration.entry_id)
    assert len(result["prices"]) == 1
    assert result["hours_requested"] == 0.25


@pytest.mark.freeze_time("2026-03-24 14:07:00-07:00")
async def test_get_prices_non_quarter_hour_rejected(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Hours must be a multiple of 0.25 according to schema validation."""
    with pytest.raises(vol.Invalid):
        await _call_get_prices(hass, 0.3, init_integration.entry_id)


@pytest.mark.freeze_time("2026-03-24 00:00:00-07:00")
async def test_get_prices_max_hours(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Requesting 24 h from midnight returns one day of quarter-hour slots."""
    result = await _call_get_prices(hass, 24, init_integration.entry_id)
    assert result["hours_requested"] == 24.0
    assert len(result["prices"]) == 96


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """get_cheapest_duration returns expected result for day range."""
    await hass.config.async_set_time_zone("UTC")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await _call_get_cheapest_duration(hass, 2.5, "day")

    assert response["duration"] == 2.5
    assert response["average_price"] == 0.266
    assert response["time_range"] == "day"
    assert response["start_time"] == "2024-01-02T06:00:00+00:00"
    assert response["end_time"] == "2024-01-02T08:30:00+00:00"
    assert response["hours_until_start"] == 22.0
    mock_api.get_cheapest_duration_day.assert_called_once()


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_night(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """get_cheapest_duration returns expected result for night range."""
    await hass.config.async_set_time_zone("UTC")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await _call_get_cheapest_duration(hass, 2.5, "night")

    assert response["duration"] == 2.5
    assert response["average_price"] == 0.258
    assert response["time_range"] == "night"
    assert response["start_time"] == "2024-01-02T00:00:00+00:00"
    assert response["end_time"] == "2024-01-02T02:30:00+00:00"
    assert response["hours_until_start"] == 16.0
    mock_api.get_cheapest_duration_night.assert_called_once()


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_full_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """get_cheapest_duration returns expected result for full day range."""
    await hass.config.async_set_time_zone("UTC")
    mock_api.get_cheapest_duration.return_value = (25.0, 12)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await _call_get_cheapest_duration(hass, 3.0, "full_day")

    assert response["duration"] == 3.0
    assert response["average_price"] == 0.25
    assert response["time_range"] == "full_day"
    assert response["start_time"] == "2024-01-01T12:00:00+00:00"
    assert response["end_time"] == "2024-01-01T15:00:00+00:00"
    assert response["hours_until_start"] == 4.0
    mock_api.get_cheapest_duration.assert_called_once()


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_default_time_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """get_cheapest_duration uses full_day as default time range."""
    await hass.config.async_set_time_zone("UTC")
    mock_api.get_cheapest_duration.return_value = (25.0, 10)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await _call_get_cheapest_duration(hass, 1.5)

    assert response["time_range"] == "full_day"
    assert response["duration"] == 1.5
    assert response["average_price"] == 0.25
    assert response["start_time"] == "2024-01-01T10:00:00+00:00"
    assert response["end_time"] == "2024-01-01T11:30:00+00:00"
    assert response["hours_until_start"] == 2.0


async def test_get_cheapest_duration_no_config_entry(hass: HomeAssistant) -> None:
    """Service raises when no integration config entry exists."""
    await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_get_cheapest_duration(hass, 2.5)
    assert exc_info.value.translation_key == "no_config_entry"


async def test_get_cheapest_duration_config_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Service raises when config entry exists but is not loaded."""
    await async_setup_component(hass, DOMAIN, {})

    mock_config_entry.add_to_hass(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_get_cheapest_duration(hass, 2.5)
    assert exc_info.value.translation_key == "config_entry_not_loaded"


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_no_data_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Service raises when cheapest-duration calculation has no data."""
    mock_api.get_cheapest_duration_day.return_value = (None, None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_get_cheapest_duration(hass, 2.5, "day")
    assert exc_info.value.translation_key == "no_data_available"


@freeze_time("2024-01-01 20:00:00+00:00")
async def test_get_cheapest_duration_past_start_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Service shifts start time to tomorrow when computed start is in the past."""
    mock_api.get_cheapest_duration_day.return_value = (26.6, 6)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await _call_get_cheapest_duration(hass, 2.5, "day")

    assert response["duration"] == 2.5
    assert response["hours_until_start"] > 0
    assert "start_time" in response
