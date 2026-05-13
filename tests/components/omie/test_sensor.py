"""Test the OMIE sensor platform."""

import datetime as dt
from unittest.mock import MagicMock

import aiohttp
from freezegun import freeze_time
from pyomie.model import OMIEResults
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import spot_price_fetcher

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor platform setup."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Should have 2 sensors (PT and ES)
    assert len(entities) == 2

    unique_ids = {entity.unique_id for entity in entities}
    expected_ids = {"pt_spot_price", "es_spot_price"}
    assert unique_ids == expected_ids


@pytest.mark.usefixtures("hass_lisbon")
async def test_sensor_state_lisbon_timezone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
    mock_omie_results_jan15: OMIEResults,
    mock_omie_results_jan16: OMIEResults,
) -> None:
    """Test sensor state updates in Lisbon timezone across publication boundary."""
    mock_config_entry.add_to_hass(hass)

    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {
            "2024-01-15": mock_omie_results_jan15,
            "2024-01-16": mock_omie_results_jan16,
        }
    )

    # Step 1: 1 PM CET (before 13:30 CET publication)
    # Lisbon day spans two CET dates: Jan 15 available, Jan 16 not yet published
    with freeze_time("2024-01-15T12:01:00Z"):  # 12:01 UTC = 12:01 Lisbon = 13:01 CET
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_pyomie.spot_price.call_count == 1

    # Step 2: 3 PM CET - verify listeners update with existing data, no new API calls
    mock_pyomie.spot_price.reset_mock()
    with freeze_time("2024-01-15T14:01:00Z"):  # 14:01 UTC = 14:01 Lisbon = 15:01 CET
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_pyomie.spot_price.call_count == 0

        pt_state_14 = hass.states.get("sensor.omie_portugal_spot_price")
        es_state_14 = hass.states.get("sensor.omie_spain_spot_price")
        assert pt_state_14.state == "351151500.0"
        assert es_state_14.state == "34151500.0"
        assert pt_state_14.attributes["unit_of_measurement"] == "€/kWh"
        assert es_state_14.attributes["unit_of_measurement"] == "€/kWh"

    # 23 UTC = 23 Lisbon = 00 CET (+1 day)
    mock_pyomie.spot_price.reset_mock()
    with freeze_time("2024-01-15T23:01:00Z"):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # CET has rolled over to the next date, one additional call to OMIE must be made.
        assert mock_pyomie.spot_price.call_count == 1
        pt_state_23 = hass.states.get("sensor.omie_portugal_spot_price")
        es_state_23 = hass.states.get("sensor.omie_spain_spot_price")
        assert pt_state_23.state == "351160000.0"
        assert es_state_23.state == "34160000.0"

    # 00 UTC (+1 day) = 00 Lisbon (+1 day) = 01 CET (+1 day)
    mock_pyomie.spot_price.reset_mock()
    with freeze_time("2024-01-16T00:31:00Z"):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # No additional API calls should be made, was already fetched at 00 PM CET
        assert mock_pyomie.spot_price.call_count == 0
        pt_state_00 = hass.states.get("sensor.omie_portugal_spot_price")
        es_state_00 = hass.states.get("sensor.omie_spain_spot_price")
        assert pt_state_00.state == "351160130.0"
        assert es_state_00.state == "34160130.0"


@pytest.mark.usefixtures("hass_madrid")
async def test_sensor_state_madrid_timezone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
    mock_omie_results_jan15: OMIEResults,
    mock_omie_results_jan16: OMIEResults,
) -> None:
    """Test sensor state updates in Madrid timezone across publication boundary."""
    mock_config_entry.add_to_hass(hass)

    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {
            "2024-01-15": mock_omie_results_jan15,
            "2024-01-16": mock_omie_results_jan16,
        }
    )

    # Step 1: 1 PM CET (before 13:30 CET publication) - only Jan 15 data available
    with freeze_time("2024-01-15T12:01:00Z"):  # 12:00 UTC = 1 PM CET (Madrid)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_pyomie.spot_price.call_count == 1

    # Step 2: 2 PM CET (after 13:30 CET publication) - Jan 16 data now available
    mock_pyomie.spot_price.reset_mock()
    with freeze_time("2024-01-15T13:01:00Z"):  # 13:00 UTC = 2 PM CET (Madrid)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # No additional call needed - Madrid only needs Jan 15 for the full day
        assert mock_pyomie.spot_price.call_count == 0

    # Step 3: 3 PM CET - verify listeners update with existing data, no new API calls
    mock_pyomie.spot_price.reset_mock()
    with freeze_time("2024-01-15T14:23:00Z"):  # 14:23 UTC = 3:23 PM CET (Madrid)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Still no additional call - Madrid doesn't need Jan 16 for Jan 15 prices
        assert mock_pyomie.spot_price.call_count == 0

        pt_state = hass.states.get("sensor.omie_portugal_spot_price")
        es_state = hass.states.get("sensor.omie_spain_spot_price")
        assert pt_state.state == "351151515.0"
        assert es_state.state == "34151515.0"
        assert pt_state.attributes["unit_of_measurement"] == "€/kWh"
        assert es_state.attributes["unit_of_measurement"] == "€/kWh"


@pytest.mark.parametrize(
    "raise_exc", [Exception("something bad"), aiohttp.ClientError("Connection timeout")]
)
async def test_sensor_unavailable_when_pyomie_throws(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
    mock_omie_results_jan15: OMIEResults,
    raise_exc: Exception,
) -> None:
    """Test sensor becomes unavailable when pyomie throws."""
    mock_config_entry.add_to_hass(hass)

    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {"2024-01-15": mock_omie_results_jan15}
    )

    # Setup at 22:01 UTC (23:01 CET, still Jan 15 in CET)
    with freeze_time("2024-01-15T22:01:00Z"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Advance to 23:16 UTC (00:16 CET Jan 16) — new CET day forces a fresh fetch
    mock_pyomie.spot_price.side_effect = raise_exc
    with freeze_time("2024-01-15T23:16:02Z"):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    pt_state = hass.states.get("sensor.omie_portugal_spot_price")
    es_state = hass.states.get("sensor.omie_spain_spot_price")
    assert pt_state.state == STATE_UNAVAILABLE
    assert es_state.state == STATE_UNAVAILABLE


async def test_sensor_unavailable_when_pyomie_returns_incomplete_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
) -> None:
    """Test sensor becomes unavailable when no data is available."""
    mock_config_entry.add_to_hass(hass)

    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {
            "2024-01-15": OMIEResults(
                updated_at=dt.datetime(2024, 1, 15, 12, 1, tzinfo=dt.UTC),
                market_date=dt.date.fromisoformat("2024-01-15"),
                contents=None,
                raw="",
            )
        }
    )

    with freeze_time("2024-01-15T12:01:00Z"):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with freeze_time("2024-01-15T12:16:02Z"):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # Both sensors should be unavailable
    pt_state = hass.states.get("sensor.omie_portugal_spot_price")
    es_state = hass.states.get("sensor.omie_spain_spot_price")
    assert pt_state.state == STATE_UNAVAILABLE
    assert es_state.state == STATE_UNAVAILABLE
