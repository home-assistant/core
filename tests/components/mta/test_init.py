"""Test the MTA New York City Transit init."""

from types import MappingProxyType
from unittest.mock import MagicMock

from pymta import MTAFeedError
import pytest

from homeassistant.components.mta.const import (
    CONF_LINE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_entry_no_subentries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up an entry without subentries."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.config_entries.async_domains()


async def test_setup_entry_with_subway_subentry(
    hass: HomeAssistant,
    mock_config_entry_with_subway_subentry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test setting up an entry with a subway subentry."""
    mock_config_entry_with_subway_subentry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    assert mock_config_entry_with_subway_subentry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.config_entries.async_domains()

    # Verify coordinator was created for the subentry
    assert len(mock_config_entry_with_subway_subentry.runtime_data) == 1


async def test_setup_entry_with_bus_subentry(
    hass: HomeAssistant,
    mock_config_entry_with_bus_subentry: MockConfigEntry,
    mock_bus_feed: MagicMock,
) -> None:
    """Test setting up an entry with a bus subentry."""
    mock_config_entry_with_bus_subentry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(
        mock_config_entry_with_bus_subentry.entry_id
    )
    await hass.async_block_till_done()

    assert mock_config_entry_with_bus_subentry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.config_entries.async_domains()

    # Verify coordinator was created for the subentry
    assert len(mock_config_entry_with_bus_subentry.runtime_data) == 1


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry_with_subway_subentry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test unloading an entry."""
    mock_config_entry_with_subway_subentry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    assert mock_config_entry_with_subway_subentry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    assert mock_config_entry_with_subway_subentry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_with_unknown_subentry_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unknown subentry types are skipped."""
    # Add a subentry with an unknown type
    unknown_subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                CONF_LINE: "1",
                CONF_STOP_ID: "127N",
                CONF_STOP_NAME: "Times Sq - 42 St",
            }
        ),
        subentry_id="01JUNKNOWN000000000000001",
        subentry_type="unknown_type",  # Unknown subentry type
        title="Unknown Subentry",
        unique_id="unknown_1",
    )
    mock_config_entry.subentries = {unknown_subentry.subentry_id: unknown_subentry}
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # No coordinators should be created for unknown subentry type
    assert len(mock_config_entry.runtime_data) == 0


async def test_setup_entry_coordinator_fetch_error(
    hass: HomeAssistant,
    mock_config_entry_with_subway_subentry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test that coordinator raises ConfigEntryNotReady on fetch error."""
    mock_subway_feed.return_value.get_arrivals.side_effect = MTAFeedError("API error")

    mock_config_entry_with_subway_subentry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    assert mock_config_entry_with_subway_subentry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.freeze_time("2023-10-21")
async def test_sensor_no_arrivals(
    hass: HomeAssistant,
    mock_config_entry_with_subway_subentry: MockConfigEntry,
    mock_subway_feed: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor values when there are no arrivals."""
    await hass.config.async_set_time_zone("UTC")

    # Return empty arrivals list
    mock_subway_feed.return_value.get_arrivals.return_value = []

    mock_config_entry_with_subway_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    # All arrival sensors should have state "unknown" (native_value is None)
    state = hass.states.get("sensor.1_times_sq_42_st_n_direction_next_arrival")
    assert state is not None
    assert state.state == "unknown"

    state = hass.states.get("sensor.1_times_sq_42_st_n_direction_second_arrival")
    assert state is not None
    assert state.state == "unknown"

    state = hass.states.get("sensor.1_times_sq_42_st_n_direction_third_arrival")
    assert state is not None
    assert state.state == "unknown"
