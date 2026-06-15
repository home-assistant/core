"""Test Green Planet Energy services."""

from unittest.mock import MagicMock

from freezegun import freeze_time
import pytest

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test get_cheapest_duration service with day time range."""
    await hass.config.async_set_time_zone("UTC")
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
    """Test get_cheapest_duration service with night time range."""
    await hass.config.async_set_time_zone("UTC")
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
    """Test get_cheapest_duration service with full_day time range."""
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
            "time_range": "full_day",
        },
        blocking=True,
        return_response=True,
    )

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
    """Test get_cheapest_duration service with default time range."""
    await hass.config.async_set_time_zone("UTC")
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
    assert response["average_price"] == 0.25
    assert response["start_time"] == "2024-01-01T10:00:00+00:00"
    assert response["end_time"] == "2024-01-01T11:30:00+00:00"
    assert response["hours_until_start"] == 2.0


async def test_get_cheapest_duration_no_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test service error when no config entry exists."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    with pytest.raises(
        ServiceValidationError,
        match="No matching integration instance was found",
    ):
        await hass.services.async_call(
            DOMAIN,
            "get_cheapest_duration",
            {"duration": 2.5},
            blocking=True,
            return_response=True,
        )


async def test_get_cheapest_duration_config_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service error when config entry is not loaded."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_config_entry.add_to_hass(hass)

    with pytest.raises(
        ServiceValidationError,
        match="This integration instance is not currently loaded",
    ):
        await hass.services.async_call(
            DOMAIN,
            "get_cheapest_duration",
            {"duration": 2.5},
            blocking=True,
            return_response=True,
        )


@freeze_time("2024-01-01 08:00:00+00:00")
async def test_get_cheapest_duration_no_data_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
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
    mock_api: MagicMock,
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
