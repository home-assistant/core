"""Test the OMIE sensor platform."""

from datetime import date, datetime
import json
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from pyomie.model import OMIEResults, SpotData
import pytest

from homeassistant.components.omie.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


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
) -> None:
    """Test sensor platform setup."""
    mock_config_entry.add_to_hass(hass)

    # Mock pyomie to return our test data
    with patch(
        "homeassistant.components.omie.coordinator.pyomie.spot_price"
    ) as mock_spot_price:
        mock_spot_price.return_value = mock_coordinator_data

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


async def test_sensor_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator_data,
) -> None:
    """Test sensor state updates with realistic data."""
    mock_config_entry.add_to_hass(hass)

    # Mock pyomie to return our test data, then None for subsequent calls
    with patch(
        "homeassistant.components.omie.coordinator.pyomie.spot_price"
    ) as mock_spot_price:
        mock_spot_price.return_value = mock_coordinator_data

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Set the coordinator data directly to the expected structure (date -> OMIEResults mapping)
        test_date = date(2024, 1, 15)
        coordinator = mock_config_entry.runtime_data
        coordinator.data = {test_date: mock_coordinator_data}

        # Mock current time to be during hour 1 (01:30) to get price index 1 from our data
        with patch("homeassistant.components.omie.sensor.utcnow") as mock_utcnow:
            # Create time for hour 1 (01:30) to get price index 1 from our mock data
            # Use fixed test date with 01:30 time in UTC
            mock_time = datetime(2024, 1, 15, 1, 30, 0, tzinfo=ZoneInfo("UTC"))
            mock_utcnow.return_value = mock_time

            # Trigger sensor updates with the mocked time
            coordinator.async_update_listeners()

    # Check sensor states - values should be converted from €/MWh to €/kWh
    pt_state = hass.states.get("sensor.omie_spot_price_portugal")
    es_state = hass.states.get("sensor.omie_spot_price_spain")

    # At 01:30 UTC (= 02:30 CET)
    # - PT price should be 39.8 €/MWh = 0.0398 €/kWh
    # - ES price should be 41.5 €/MWh = 0.0415 €/kWh
    assert pt_state.state == "0.0398"
    assert es_state.state == "0.0415"

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


async def test_coordinator_unavailability_logging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator logs unavailability and recovery appropriately."""
    mock_config_entry.add_to_hass(hass)

    # Set up coordinator with successful initial setup
    with patch(
        "homeassistant.components.omie.coordinator.pyomie.spot_price"
    ) as mock_spot_price:
        # Initial successful setup
        mock_spot_price.return_value = None  # No data but no error

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Clear any initial logs
        caplog.clear()

        # Mock API failure
        mock_spot_price.side_effect = Exception("Connection timeout")

        # Get coordinator from config entry runtime data
        coordinator = mock_config_entry.runtime_data

        # Trigger coordinator refresh (simulate update interval)
        await coordinator.async_refresh()

        # Check that error was logged
        assert "Error fetching omie data: Connection timeout" in caplog.text

        # Clear logs to test log-once behavior
        caplog.clear()

        # Second failure should not log again
        await coordinator.async_refresh()
        assert "Error fetching omie data" not in caplog.text  # Should not log again

        # Mock API recovery
        mock_spot_price.side_effect = None
        mock_spot_price.return_value = None

        # Trigger recovery
        await coordinator.async_refresh()

        # Check recovery message was logged
        assert "Fetching omie data recovered" in caplog.text
