"""Test the OMIE sensor platform."""

import datetime as dt
import logging

from freezegun import freeze_time
from pyomie.model import OMIEResults
import pytest

from homeassistant.components.omie.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import spot_price_fetcher

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="OMIE",
        domain=DOMAIN,
        unique_id="omie_singleton",
    )


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie,
) -> None:
    """Test sensor platform setup."""
    mock_config_entry.add_to_hass(hass)

    mock_pyomie.spot_price.side_effect = spot_price_fetcher({})

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that entities were created
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Should have 2 sensors (PT and ES)
    assert len(entities) == 2

    # Check entity unique IDs
    entity_ids = {entity.unique_id for entity in entities}
    expected_ids = {"spot_price_pt", "spot_price_es"}
    assert entity_ids == expected_ids


async def test_sensor_state_lisbon_timezone(
    hass_lisbon: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie,
    mock_omie_results_jan15,
    mock_omie_results_jan16,
) -> None:
    """Test sensor state updates in Lisbon timezone across publication boundary."""
    mock_config_entry.add_to_hass(hass_lisbon)

    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {
            "2024-01-15": mock_omie_results_jan15,
            "2024-01-16": mock_omie_results_jan16,
        }
    )

    # Step 1: 1 PM CET (before 13:30 CET publication)
    # Lisbon day spans two CET dates: Jan 15 available, Jan 16 not yet published
    with freeze_time("2024-01-15T12:01:00Z"):  # 12:01 UTC = 12:01 Lisbon = 13:01 CET
        assert await hass_lisbon.config_entries.async_setup(mock_config_entry.entry_id)
        await hass_lisbon.async_block_till_done()

        # Only 1 API call for Jan 15 (Jan 16 not yet published at 13:30 CET)
        assert mock_pyomie.spot_price.call_count == 1

    # Step 2: 2 PM CET (after 13:30 CET publication) - Jan 16 now available
    with freeze_time("2024-01-15T13:01:00Z"):  # 13:01 UTC = 13:01 Lisbon = 14:01 CET
        async_fire_time_changed(hass_lisbon, dt_util.utcnow())
        await hass_lisbon.async_block_till_done()

        # Additional call for Jan 16 (now published, needed for Lisbon's full day)
        assert mock_pyomie.spot_price.call_count == 2

    # Step 3: 3 PM CET - verify listeners update with existing data, no new API calls
    with freeze_time("2024-01-15T14:01:00Z"):  # 14:01 UTC = 14:01 Lisbon = 15:01 CET
        async_fire_time_changed(hass_lisbon, dt_util.utcnow())
        await hass_lisbon.async_block_till_done()

        # No additional API calls should be made
        assert mock_pyomie.spot_price.call_count == 2

        # Check sensor states - values should be converted from €/MWh to €/kWh
        pt_state_14 = hass_lisbon.states.get("sensor.omie_portugal_spot_price")
        es_state_14 = hass_lisbon.states.get("sensor.omie_spain_spot_price")

        # At 14:00 UTC (= 14:00 Lisbon = 3 PM CET)
        assert pt_state_14.state[:8] == "351.1515"  # (PT day 15, hour 15)
        assert es_state_14.state[:7] == "34.1515"  # (ES day 15, hour 15)

        # Check units are correct
        assert pt_state_14.attributes["unit_of_measurement"] == "€/kWh"
        assert es_state_14.attributes["unit_of_measurement"] == "€/kWh"

    # 23 UTC = 23 Lisbon = 00 CET (+1 day)
    with freeze_time("2024-01-15T23:01:00Z"):
        async_fire_time_changed(hass_lisbon, dt_util.utcnow())
        await hass_lisbon.async_block_till_done()

        # No additional API calls should be made, was already fetched at 3 PM CET
        assert mock_pyomie.spot_price.call_count == 2

        # Check sensor states - values should be converted from €/MWh to €/kWh
        pt_state_23 = hass_lisbon.states.get("sensor.omie_portugal_spot_price")
        es_state_23 = hass_lisbon.states.get("sensor.omie_spain_spot_price")

        # At 14:00 UTC (= 14:00 Lisbon = 3 PM CET)
        assert pt_state_23.state[:8] == "351.16"  # (PT day 16, hour 00)
        assert es_state_23.state[:7] == "34.16"  # (ES day 16, hour 00)

    # 00 UTC (+1 day) = 00 Lisbon (+1 day) = 01 CET (+1 day)
    with freeze_time("2024-01-16T00:01:00Z"):
        async_fire_time_changed(hass_lisbon, dt_util.utcnow())
        await hass_lisbon.async_block_till_done()

        # No additional API calls should be made, was already fetched at 3 PM CET
        assert mock_pyomie.spot_price.call_count == 2

        # Check sensor states - values should be converted from €/MWh to €/kWh
        pt_state_00 = hass_lisbon.states.get("sensor.omie_portugal_spot_price")
        es_state_00 = hass_lisbon.states.get("sensor.omie_spain_spot_price")

        # At 00 UTC (= 00 Lisbon = 1 AM CET)
        assert pt_state_00.state[:8] == "351.1601"  # (PT day 16, hour 01)
        assert es_state_00.state[:7] == "34.1601"  # (ES day 16, hour 01)


async def test_sensor_state_madrid_timezone(
    hass_madrid: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie,
    mock_omie_results_jan15,
    mock_omie_results_jan16,
) -> None:
    """Test sensor state updates in Madrid timezone across publication boundary."""
    mock_config_entry.add_to_hass(hass_madrid)

    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {
            "2024-01-15": mock_omie_results_jan15,
            "2024-01-16": mock_omie_results_jan16,
        }
    )

    # Step 1: 1 PM CET (before 13:30 CET publication) - only Jan 15 data available
    with freeze_time("2024-01-15T12:01:00Z"):  # 12:00 UTC = 1 PM CET (Madrid)
        assert await hass_madrid.config_entries.async_setup(mock_config_entry.entry_id)
        await hass_madrid.async_block_till_done()

        # Should only have 1 API call for Jan 15 (Jan 16 not yet published)
        assert mock_pyomie.spot_price.call_count == 1

    # Step 2: 2 PM CET (after 13:30 CET publication) - Jan 16 data now available
    with freeze_time("2024-01-15T13:01:00Z"):  # 13:00 UTC = 2 PM CET (Madrid)
        async_fire_time_changed(hass_madrid, dt_util.utcnow())
        await hass_madrid.async_block_till_done()

        # No additional call needed - Madrid only needs Jan 15 for the full day
        assert mock_pyomie.spot_price.call_count == 1

    # Step 3: 3 PM CET - verify listeners update with existing data, no new API calls
    with freeze_time("2024-01-15T14:01:00Z"):  # 14:00 UTC = 3 PM CET (Madrid)
        async_fire_time_changed(hass_madrid, dt_util.utcnow())
        await hass_madrid.async_block_till_done()

        # Still only 1 API call - Madrid doesn't need Jan 16 for Jan 15 prices
        assert mock_pyomie.spot_price.call_count == 1

        # Check sensor states - values should be converted from €/MWh to €/kWh
        pt_state = hass_madrid.states.get("sensor.omie_portugal_spot_price")
        es_state = hass_madrid.states.get("sensor.omie_spain_spot_price")

        # At 14:00 UTC ( = 3 PM CET)
        assert pt_state.state[:8] == "351.1515"  # (PT day 15, hour 15)
        assert es_state.state[:7] == "34.1515"  # (ES day 15, hour 15)

        # Check units are correct
        assert pt_state.attributes["unit_of_measurement"] == "€/kWh"
        assert es_state.attributes["unit_of_measurement"] == "€/kWh"


async def test_sensor_unavailable_when_pyomie_throws(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie,
) -> None:
    """Test sensor becomes unavailable when no data is available."""
    mock_config_entry.add_to_hass(hass)

    mock_pyomie.spot_price.side_effect = Exception("something bad")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Both sensors should be unavailable
    pt_state = hass.states.get("sensor.omie_portugal_spot_price")
    es_state = hass.states.get("sensor.omie_spain_spot_price")

    assert pt_state.state == "unavailable"
    assert es_state.state == "unavailable"


async def test_sensor_unavailable_when_pyomie_returns_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie,
) -> None:
    """Test sensor becomes unavailable when no data is available."""
    mock_config_entry.add_to_hass(hass)

    mock_pyomie.spot_price.side_effect = spot_price_fetcher({})

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Both sensors should be unavailable
    pt_state = hass.states.get("sensor.omie_portugal_spot_price")
    es_state = hass.states.get("sensor.omie_spain_spot_price")

    assert pt_state.state == "unavailable"
    assert es_state.state == "unavailable"


@freeze_time("2024-01-15T12:01:00Z")
async def test_sensor_unavailable_when_pyomie_returns_incomplete_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie,
) -> None:
    """Test sensor becomes unavailable when no data is available."""
    mock_config_entry.add_to_hass(hass)

    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {
            "2024-01-15": OMIEResults(
                updated_at=dt.datetime.now(),
                market_date=dt.date.fromisoformat("2024-01-15"),
                contents=None,
                raw="",
            )
        }
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Both sensors should be unavailable
    pt_state = hass.states.get("sensor.omie_portugal_spot_price")
    es_state = hass.states.get("sensor.omie_spain_spot_price")

    assert pt_state.state == "unavailable"
    assert es_state.state == "unavailable"


@freeze_time("2024-01-16 12:00:00")
async def test_coordinator_unavailability_logging(
    hass_madrid: HomeAssistant,
    mock_pyomie,
    mock_omie_results_jan16,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator logs unavailability and recovery appropriately."""
    caplog.set_level(logging.INFO)
    hass = hass_madrid
    mock_config_entry.add_to_hass(hass)

    # Initial successful setup
    mock_pyomie.spot_price.reset_mock()
    mock_pyomie.spot_price.side_effect = spot_price_fetcher({})

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_pyomie.spot_price.call_count == 1
    assert "ERROR" not in caplog.text

    # Mock API failure
    mock_pyomie.spot_price.side_effect = Exception("Connection timeout")

    # Get coordinator from config entry runtime data
    coordinator = mock_config_entry.runtime_data

    # Trigger coordinator refresh (simulate update interval)
    await coordinator.async_refresh()

    assert mock_pyomie.spot_price.call_count == 2
    assert "Unexpected error fetching omie data" in caplog.text
    assert "Connection timeout" in caplog.text

    # Second failure should not log again
    caplog.clear()
    await coordinator.async_refresh()
    assert mock_pyomie.spot_price.call_count == 3
    assert "Error" not in caplog.text  # Should not log again

    # Mock API recovery
    mock_pyomie.spot_price.side_effect = spot_price_fetcher({})

    # Trigger recovery
    await coordinator.async_refresh()
    assert mock_pyomie.spot_price.call_count == 4
    assert "Fetching omie data recovered" in caplog.text
