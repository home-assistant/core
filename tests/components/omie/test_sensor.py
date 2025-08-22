"""Test the OMIE sensor platform."""

from datetime import date, datetime
import json
import logging
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from pyomie.model import OMIEResults, SpotData
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


@pytest.fixture
def mock_coordinator_data():
    """Return mock OMIEResults that pyomie.spot_price would return."""
    # Use fixed test date for deterministic testing
    today = date(2024, 1, 15)

    # hourly price data (24 hours in €/MWh)
    hourly_prices_pt = [
        45.5,
        42.3,
        39.8,
        38.2,
        37.5,
        36.9,
        41.2,
        48.7,
        55.3,
        62.1,
        68.4,
        72.6,
        75.1,
        78.3,
        76.8,
        74.2,
        82.5,
        85.7,
        89.3,
        87.1,
        65.8,
        58.4,
        52.1,
        48.7,
    ]

    hourly_prices_es = [
        47.1,
        44.2,
        41.5,
        39.9,
        38.8,
        38.1,
        42.8,
        50.3,
        57.2,
        64.7,
        70.2,
        74.8,
        77.5,
        80.1,
        78.6,
        76.0,
        84.2,
        87.8,
        91.4,
        89.1,
        67.5,
        60.1,
        54.3,
        50.4,
    ]

    # Create proper SpotData structure
    spot_data = SpotData(
        url="https://example.com",
        market_date=today.isoformat(),
        header="Test Data",
        energy_total_es_pt=[],
        energy_purchases_es=[],
        energy_purchases_pt=[],
        energy_sales_es=[],
        energy_sales_pt=[],
        energy_es_pt=[],
        energy_export_es_to_pt=[],
        energy_import_es_from_pt=[],
        spot_price_es=hourly_prices_es,  # The data our sensors need
        spot_price_pt=hourly_prices_pt,  # The data our sensors need
    )

    # Return OMIEResults directly (what pyomie.spot_price returns)
    return OMIEResults(
        updated_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("Europe/Lisbon")),
        market_date=today,
        contents=spot_data,
        raw=json.dumps(spot_data),
    )


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator_data,
    mock_pyomie,
) -> None:
    """Test sensor platform setup."""
    mock_config_entry.add_to_hass(hass)

    mock_pyomie.spot_price.return_value = mock_coordinator_data

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
        pt_state_14 = hass_lisbon.states.get("sensor.omie_spot_price_portugal")
        es_state_14 = hass_lisbon.states.get("sensor.omie_spot_price_spain")

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
        pt_state_23 = hass_lisbon.states.get("sensor.omie_spot_price_portugal")
        es_state_23 = hass_lisbon.states.get("sensor.omie_spot_price_spain")

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
        pt_state_00 = hass_lisbon.states.get("sensor.omie_spot_price_portugal")
        es_state_00 = hass_lisbon.states.get("sensor.omie_spot_price_spain")

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
        pt_state = hass_madrid.states.get("sensor.omie_spot_price_portugal")
        es_state = hass_madrid.states.get("sensor.omie_spot_price_spain")

        # At 14:00 UTC ( = 3 PM CET)
        assert pt_state.state[:8] == "351.1515"  # (PT day 15, hour 15)
        assert es_state.state[:7] == "34.1515"  # (ES day 15, hour 15)

        # Check units are correct
        assert pt_state.attributes["unit_of_measurement"] == "€/kWh"
        assert es_state.attributes["unit_of_measurement"] == "€/kWh"


async def test_sensor_unavailable_when_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor becomes unavailable when no data is available."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with no data
    with patch(
        "homeassistant.components.omie.coordinator.OMIECoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.data = {}  # No data
        mock_coordinator.async_add_listener = MagicMock()

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Both sensors should be unavailable
    pt_state = hass.states.get("sensor.omie_spot_price_portugal")
    es_state = hass.states.get("sensor.omie_spot_price_spain")

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
    assert "Error fetching omie data: Connection timeout" in caplog.text

    # Clear logs to test log-once behavior
    caplog_text_before = caplog.text

    # Second failure should not log again
    await coordinator.async_refresh()
    assert mock_pyomie.spot_price.call_count == 3
    assert caplog.text == caplog_text_before  # Should not log again

    # Mock API recovery
    mock_pyomie.spot_price.side_effect = spot_price_fetcher({})

    # Trigger recovery
    await coordinator.async_refresh()
    assert mock_pyomie.spot_price.call_count == 4
    assert "Fetching omie data recovered" in caplog.text
