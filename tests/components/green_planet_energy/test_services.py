"""Test Green Planet Energy services."""

from freezegun import freeze_time
import pytest

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test get_cheapest_duration service with day time range."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        {
            "duration": 2.5,
            "time_range": "day",
        },
        blocking=True,
        return_response=True,
    )

    assert response["duration"] == 2.5
    assert response["average_price"] == 0.266
    assert response["time_range"] == "day"
    assert "start_time" in response
    assert "end_time" in response
    assert "hours_until_start" in response
    mock_api.get_cheapest_duration_day.assert_called_once()


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_night(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test get_cheapest_duration service with night time range."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        {
            "duration": 2.5,
            "time_range": "night",
        },
        blocking=True,
        return_response=True,
    )

    assert response["duration"] == 2.5
    assert response["average_price"] == 0.258
    assert response["time_range"] == "night"
    assert "start_time" in response
    assert "end_time" in response
    assert "hours_until_start" in response
    mock_api.get_cheapest_duration_night.assert_called_once()


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_full_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test get_cheapest_duration service with full_day time range."""
    mock_api.get_cheapest_duration.return_value = (25.0, 12)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        {
            "duration": 3.0,
            "time_range": "full_day",
        },
        blocking=True,
        return_response=True,
    )

    assert response["duration"] == 3.0
    assert response["average_price"] == 0.25
    assert response["time_range"] == "full_day"
    assert "start_time" in response
    assert "end_time" in response
    assert "hours_until_start" in response
    mock_api.get_cheapest_duration.assert_called_once()


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_default_time_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test get_cheapest_duration service with default time range."""
    mock_api.get_cheapest_duration.return_value = (25.0, 10)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        {
            "duration": 1.5,
        },
        blocking=True,
        return_response=True,
    )

    assert response["time_range"] == "full_day"
    assert response["duration"] == 1.5


async def test_get_cheapest_duration_no_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test service when no config entry exists."""
    # Service should not be registered without a config entry
    assert not hass.services.has_service(DOMAIN, "get_cheapest_duration")


async def test_get_cheapest_duration_config_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service when config entry is not loaded."""
    mock_config_entry.add_to_hass(hass)
    # Don't call async_setup to leave entry unloaded

    # Service should not be registered until entry is loaded
    assert not hass.services.has_service(DOMAIN, "get_cheapest_duration")


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_no_data_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test service fails when no price data is available."""
    mock_api.get_cheapest_duration_day.return_value = (None, None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(
        ServiceValidationError,
        match="No price data available for the requested duration and time range",
    ):
        await hass.services.async_call(
            DOMAIN,
            "get_cheapest_duration",
            {
                "duration": 2.5,
                "time_range": "day",
            },
            blocking=True,
            return_response=True,
        )


@freeze_time("2024-01-01 20:00:00+00:00")
async def test_get_cheapest_duration_past_start_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test service handles start times that are in the past (tomorrow)."""
    # Mock returns hour 6, but we're at hour 20, so result should be tomorrow
    mock_api.get_cheapest_duration_day.return_value = (26.6, 6)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        {
            "duration": 2.5,
            "time_range": "day",
        },
        blocking=True,
        return_response=True,
    )

    # Start time should be tomorrow since we're past 6:00 today
    # hours_until_start should be positive (sometime in the future)
    assert response["duration"] == 2.5
    assert response["hours_until_start"] > 0
    assert "start_time" in response


@freeze_time("2024-01-01 06:00:00+00:00")
async def test_get_price_schedule_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test price_schedule mode returns 15-minute resolution prices within the cheapest window."""
    # Freeze at 06:00 UTC so the mock's start_hour=6 is exactly "now" (not in the
    # past), and use UTC to make current_hour predictable across environments.
    await hass.config.async_set_time_zone("UTC")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        {
            "duration": 2.5,
            "mode": "price_schedule",
            "time_range": "day",
        },
        blocking=True,
        return_response=True,
    )

    assert response["time_range"] == "day"
    assert "T06:00:00" in response["start_time"]
    assert "T08:30:00" in response["end_time"]

    prices = response["prices"]
    # 2.5h = 150 minutes → 10 slots of 15 minutes each
    assert len(prices) == 10

    # Every slot must have the three required fields
    for slot in prices:
        assert "start_time" in slot
        assert "end_time" in slot
        assert "price" in slot

    # First slot: 06:00 → gpe_price_06_00 = 26.0 Cent/kWh → 0.26 €/kWh
    assert prices[0]["price"] == 0.26
    assert "T06:00:00" in prices[0]["start_time"]
    assert "T06:15:00" in prices[0]["end_time"]

    # Second slot: 06:15 → gpe_price_06_15 = 26.15 Cent/kWh → 0.2615 €/kWh
    assert prices[1]["price"] == 0.2615
    assert "T06:15:00" in prices[1]["start_time"]

    # Last slot: 08:15 → gpe_price_08_15 = 28.15 Cent/kWh → 0.2815 €/kWh
    assert prices[-1]["price"] == 0.2815
    assert "T08:15:00" in prices[-1]["start_time"]
    assert "T08:30:00" in prices[-1]["end_time"]


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_price_schedule_night(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test price_schedule mode for night range returns tomorrow's data for early-morning slots."""
    # At 08:00 UTC the mock's start_hour=0 is in the past so it shifts to 2024-01-02.
    # Hours 0-5 on that day are served by _tomorrow keys in the price data.
    await hass.config.async_set_time_zone("UTC")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        {
            "duration": 2.5,
            "mode": "price_schedule",
            "time_range": "night",
        },
        blocking=True,
        return_response=True,
    )

    assert response["time_range"] == "night"
    prices = response["prices"]
    # 2.5h = 150 minutes → 10 slots of 15 minutes
    assert len(prices) == 10

    # Hours 0-5 are early morning → gpe_price_HH_MM_tomorrow keys
    # Slot 00:00 tomorrow: gpe_price_00_00_tomorrow = 25.0 Cent/kWh → 0.25 €/kWh
    assert prices[0]["price"] == 0.25
    assert "2024-01-02" in prices[0]["start_time"]
    assert "T00:00:00" in prices[0]["start_time"]
    assert "T00:15:00" in prices[0]["end_time"]

    # Slot 00:15 tomorrow: gpe_price_00_15_tomorrow = 25.15 Cent/kWh → 0.2515 €/kWh
    assert prices[1]["price"] == 0.2515

    # Last slot: 02:15 tomorrow: gpe_price_02_15_tomorrow = 27.15 Cent/kWh → 0.2715 €/kWh
    assert prices[-1]["price"] == 0.2715
    assert "T02:15:00" in prices[-1]["start_time"]
    assert "T02:30:00" in prices[-1]["end_time"]


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_price_schedule_full_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test price_schedule mode for full_day returns 15-min prices within the window."""
    # At 08:00 UTC the mock's start_hour=12 is in the future so no date shift occurs.
    await hass.config.async_set_time_zone("UTC")
    mock_api.get_cheapest_duration.return_value = (25.0, 12)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        {
            "duration": 3.0,
            "mode": "price_schedule",
            "time_range": "full_day",
        },
        blocking=True,
        return_response=True,
    )

    assert response["time_range"] == "full_day"
    assert "T12:00:00" in response["start_time"]
    assert "T15:00:00" in response["end_time"]

    prices = response["prices"]
    # 3h = 180 minutes → 12 slots of 15 minutes
    assert len(prices) == 12

    # First slot: 12:00 → gpe_price_12_00 = 32.0 Cent/kWh → 0.32 €/kWh
    assert prices[0]["price"] == 0.32
    assert "T12:00:00" in prices[0]["start_time"]
    assert "T12:15:00" in prices[0]["end_time"]

    # Second slot: 12:15 → gpe_price_12_15 = 32.15 Cent/kWh → 0.3215 €/kWh
    assert prices[1]["price"] == 0.3215

    # Last slot: 14:45 → gpe_price_14_45 = 34.45 Cent/kWh → 0.3445 €/kWh
    assert prices[-1]["price"] == 0.3445
    assert "T14:45:00" in prices[-1]["start_time"]
    assert "T15:00:00" in prices[-1]["end_time"]


@freeze_time("2024-01-01 14:00:00+00:00")
async def test_get_price_schedule_night_evening_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test price_schedule mode for night range with an evening start hour (>= 18:00).

    Covers the branch in _build_window_price_schedule where use_tomorrow=True but
    the slot hour is >= 18 (evening slots that belong to today's price data, not
    tomorrow's).
    """
    # Cheapest 2h night window starting at 20:00 (still today, so no date shift).
    await hass.config.async_set_time_zone("UTC")
    mock_api.get_cheapest_duration_night.return_value = (40.0, 20)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_duration",
        {
            "duration": 2.0,
            "mode": "price_schedule",
            "time_range": "night",
        },
        blocking=True,
        return_response=True,
    )

    assert response["time_range"] == "night"
    assert "T20:00:00" in response["start_time"]
    assert "T22:00:00" in response["end_time"]

    prices = response["prices"]
    # 2h = 120 minutes → 8 slots of 15 minutes each
    assert len(prices) == 8

    # Evening slots use today's keys (no _tomorrow suffix).
    # Slot 20:00 → gpe_price_20_00 = 40.0 Cent/kWh → 0.40 €/kWh
    assert prices[0]["price"] == 0.40
    assert "T20:00:00" in prices[0]["start_time"]
    assert "T20:15:00" in prices[0]["end_time"]

    # Slot 21:45 → gpe_price_21_45 = 41.45 Cent/kWh → 0.4145 €/kWh
    assert prices[-1]["price"] == 0.4145
    assert "T21:45:00" in prices[-1]["start_time"]
    assert "T22:00:00" in prices[-1]["end_time"]
