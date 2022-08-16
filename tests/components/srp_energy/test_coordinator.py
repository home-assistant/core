"""Test the SRP Energy sensor coordinator."""
from datetime import datetime, timedelta
import logging

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.srp_energy import (
    DOMAIN,
    TIME_DELTA_BETWEEN_API_UPDATES,
    TIME_DELTA_BETWEEN_UPDATES,
)
from homeassistant.components.srp_energy.coordinator import SrpCoordinator
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_loading_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_tz_info,
    mock_config_entry,
    mock_srp_energy,
) -> None:
    """Test loading data from coordinator."""
    now = datetime(2022, 8, 2, 0, 0, 0, 0, tzinfo=hass_tz_info)
    freezer.move_to(now)
    mock_end_date = now
    mock_start_date = now - timedelta(days=45)

    _LOGGER.debug("Test: Starting setup at test_time: %s", dt_util.utcnow())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: SrpCoordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    assert coordinator.update_interval == TIME_DELTA_BETWEEN_UPDATES
    assert coordinator.data["energy_usage_this_day"] == 2.0
    assert coordinator.data["energy_usage_price_this_day"] == 0.30
    assert coordinator.data["energy_usage_this_month"] == 69.4
    assert coordinator.data["energy_usage_price_this_month"] == 10.02
    assert coordinator.data["energy_usage_this_day_1_day_ago"] == 1.8
    assert coordinator.data["energy_usage_price_this_day_1_day_ago"] == 0.26
    assert coordinator.data["energy_usage_this_month_1_day_ago"] == 1.8
    assert coordinator.data["energy_usage_price_this_month_1_day_ago"] == 0.26

    # Check Past 48 hrs Usage
    assert len(coordinator.data["hourly_energy_usage_past_48hr"]) == 48
    assert coordinator.data["hourly_energy_usage_past_48hr"][
        "2022-07-31T01:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "01:00 AM",
        "iso_date": "2022-07-31T01:00:00",
        "value": 1.3,
    }
    assert coordinator.data["hourly_energy_usage_past_48hr"][
        "2022-08-02T00:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-08-02T00:00:00",
        "value": 2,
    }

    # Check Past 48 hrs Usage Price
    assert len(coordinator.data["hourly_energy_usage_price_past_48hr"]) == 48
    assert coordinator.data["hourly_energy_usage_price_past_48hr"][
        "2022-07-31T01:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "01:00 AM",
        "iso_date": "2022-07-31T01:00:00",
        "value": 0.2,
    }
    assert coordinator.data["hourly_energy_usage_price_past_48hr"][
        "2022-08-02T00:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-08-02T00:00:00",
        "value": 0.3,
    }

    # Check Past 2 Weeks Usage
    assert len(coordinator.data["daily_energy_usage_past_2weeks"]) == 3
    assert coordinator.data["daily_energy_usage_past_2weeks"][
        "2022-07-31T00:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-07-31T00:00:00",
        "value": 56.9,
    }
    assert coordinator.data["daily_energy_usage_past_2weeks"][
        "2022-08-02T00:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-08-02T00:00:00",
        "value": 2,
    }

    # Check Past 2 Weeks Usage Price
    assert len(coordinator.data["daily_energy_usage_price_past_2weeks"]) == 3
    assert coordinator.data["daily_energy_usage_price_past_2weeks"][
        "2022-07-31T00:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-07-31T00:00:00",
        "value": 8.23,
    }
    assert coordinator.data["daily_energy_usage_price_past_2weeks"][
        "2022-08-02T00:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-08-02T00:00:00",
        "value": 0.3,
    }

    mock_srp_energy.usage.assert_called_once_with(
        dt_util.as_utc(mock_start_date), dt_util.as_utc(mock_end_date), False
    )
    assert mock_srp_energy.usage.call_count == 1


async def test_data_refresh(
    hass: HomeAssistant, freezer, hass_tz_info, mock_config_entry, mock_srp_energy
) -> None:
    """Test refreshing data in coordinator."""

    now = datetime(2022, 8, 2, 0, 0, 0, 0, tzinfo=hass_tz_info)
    freezer.move_to(now)
    mock_end_date = now
    mock_start_date = now - timedelta(days=45)

    _LOGGER.debug("Test: Starting setup at test_time: %s", dt_util.utcnow())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: SrpCoordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # API Client shouldn't be called
    future = now + (2 * TIME_DELTA_BETWEEN_UPDATES)
    _LOGGER.debug(
        "Test: Trigger short time delay for %s at %s", future, dt_util.utcnow()
    )
    freezer.move_to(future)
    _LOGGER.debug("Test: time is now %s", dt_util.utcnow())
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert coordinator.data["energy_usage_this_day"] == 4.0
    assert coordinator.data["energy_usage_price_this_day"] == 0.59
    assert coordinator.data["energy_usage_this_month"] == 71.4
    assert coordinator.data["energy_usage_price_this_month"] == 10.31
    assert coordinator.data["energy_usage_this_day_1_day_ago"] == 3.5
    assert coordinator.data["energy_usage_price_this_day_1_day_ago"] == 0.52
    assert coordinator.data["energy_usage_this_month_1_day_ago"] == 3.5
    assert coordinator.data["energy_usage_price_this_month_1_day_ago"] == 0.52

    # Check Past 48 hrs Usage
    assert len(coordinator.data["hourly_energy_usage_past_48hr"]) == 48
    assert coordinator.data["hourly_energy_usage_past_48hr"][
        "2022-07-31T02:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "02:00 AM",
        "iso_date": "2022-07-31T02:00:00",
        "value": 1.1,
    }
    assert coordinator.data["hourly_energy_usage_past_48hr"][
        "2022-08-02T01:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "01:00 AM",
        "iso_date": "2022-08-02T01:00:00",
        "value": 2,
    }

    # Check Past 48 hrs Usage Price
    assert len(coordinator.data["hourly_energy_usage_price_past_48hr"]) == 48
    assert coordinator.data["hourly_energy_usage_price_past_48hr"][
        "2022-07-31T02:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "02:00 AM",
        "iso_date": "2022-07-31T02:00:00",
        "value": 0.17,
    }
    assert coordinator.data["hourly_energy_usage_price_past_48hr"][
        "2022-08-02T01:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "01:00 AM",
        "iso_date": "2022-08-02T01:00:00",
        "value": 0.29,
    }

    # Check Past 2 Weeks Usage
    assert len(coordinator.data["daily_energy_usage_past_2weeks"]) == 3
    assert coordinator.data["daily_energy_usage_past_2weeks"][
        "2022-07-31T00:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-07-31T00:00:00",
        "value": 56.9,
    }
    assert coordinator.data["daily_energy_usage_past_2weeks"][
        "2022-08-02T00:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-08-02T00:00:00",
        "value": 4,
    }

    # Check Past 2 Weeks Usage Price
    assert len(coordinator.data["daily_energy_usage_price_past_2weeks"]) == 3
    assert coordinator.data["daily_energy_usage_price_past_2weeks"][
        "2022-07-31T00:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-07-31T00:00:00",
        "value": 8.23,
    }
    assert coordinator.data["daily_energy_usage_price_past_2weeks"][
        "2022-08-02T00:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-08-02T00:00:00",
        "value": 0.59,
    }

    mock_srp_energy.usage.assert_called_once_with(
        dt_util.as_utc(mock_start_date), dt_util.as_utc(mock_end_date), False
    )
    assert mock_srp_energy.usage.call_count == 1


async def test_api_data_refresh(
    hass: HomeAssistant, freezer, hass_tz_info, mock_config_entry, mock_srp_energy
) -> None:
    """Test refreshing api data in coordinator."""

    now = datetime(2022, 8, 2, 0, 0, 0, 0, tzinfo=hass_tz_info)
    freezer.move_to(now)
    mock_end_date = now
    mock_start_date = now - timedelta(days=45)

    _LOGGER.debug("Test: Starting setup at test_time: %s", dt_util.utcnow())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: SrpCoordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # API Client shouldn't be called
    future = now + (2 * TIME_DELTA_BETWEEN_UPDATES)
    _LOGGER.debug(
        "Test: Trigger short time delay for %s at %s", future, dt_util.utcnow()
    )
    freezer.move_to(future)
    _LOGGER.debug("Test: time is now %s", dt_util.utcnow())
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    mock_srp_energy.usage.assert_called_once_with(
        dt_util.as_utc(mock_start_date), dt_util.as_utc(mock_end_date), False
    )
    assert mock_srp_energy.usage.call_count == 1

    # API Clien should not be called.
    future = now + TIME_DELTA_BETWEEN_API_UPDATES
    _LOGGER.debug(
        "Test: Trigger long time delay for %s at %s", future, dt_util.utcnow()
    )
    freezer.move_to(future)
    _LOGGER.debug("Test: time is now %s", dt_util.utcnow())
    async_fire_time_changed(hass, future)
    _LOGGER.debug("Test: block till done")
    await hass.async_block_till_done()

    assert coordinator.data["energy_usage_this_day"] == 18.3
    assert coordinator.data["energy_usage_price_this_day"] == 2.67
    assert coordinator.data["energy_usage_this_month"] == 85.7
    assert coordinator.data["energy_usage_price_this_month"] == 12.39
    assert coordinator.data["energy_usage_this_day_1_day_ago"] == 15.6
    assert coordinator.data["energy_usage_price_this_day_1_day_ago"] == 2.31
    assert coordinator.data["energy_usage_this_month_1_day_ago"] == 15.6
    assert coordinator.data["energy_usage_price_this_month_1_day_ago"] == 2.31

    # Check Past 48 hrs Usage
    assert len(coordinator.data["hourly_energy_usage_past_48hr"]) == 48
    assert coordinator.data["hourly_energy_usage_past_48hr"][
        "2022-07-31T09:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "09:00 AM",
        "iso_date": "2022-07-31T09:00:00",
        "value": 0.7,
    }
    assert coordinator.data["hourly_energy_usage_past_48hr"][
        "2022-08-02T08:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "08:00 AM",
        "iso_date": "2022-08-02T08:00:00",
        "value": 2.4,
    }

    # Check Past 48 hrs Usage Price
    assert len(coordinator.data["hourly_energy_usage_price_past_48hr"]) == 48
    assert coordinator.data["hourly_energy_usage_price_past_48hr"][
        "2022-07-31T09:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "09:00 AM",
        "iso_date": "2022-07-31T09:00:00",
        "value": 0.12,
    }
    assert coordinator.data["hourly_energy_usage_price_past_48hr"][
        "2022-08-02T08:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "08:00 AM",
        "iso_date": "2022-08-02T08:00:00",
        "value": 0.34,
    }

    # Check Past 2 Weeks Usage
    assert len(coordinator.data["daily_energy_usage_past_2weeks"]) == 3
    assert coordinator.data["daily_energy_usage_past_2weeks"][
        "2022-07-31T00:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-07-31T00:00:00",
        "value": 56.9,
    }
    assert coordinator.data["daily_energy_usage_past_2weeks"][
        "2022-08-02T00:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-08-02T00:00:00",
        "value": 18.3,
    }

    # Check Past 2 Weeks Usage Price
    assert len(coordinator.data["daily_energy_usage_price_past_2weeks"]) == 3
    assert coordinator.data["daily_energy_usage_price_past_2weeks"][
        "2022-07-31T00:00:00-0700"
    ] == {
        "day": "7/31/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-07-31T00:00:00",
        "value": 8.23,
    }
    assert coordinator.data["daily_energy_usage_price_past_2weeks"][
        "2022-08-02T00:00:00-0700"
    ] == {
        "day": "8/02/2022",
        "hour": "00:00 AM",
        "iso_date": "2022-08-02T00:00:00",
        "value": 2.67,
    }

    assert mock_srp_energy.usage.call_count == 2
