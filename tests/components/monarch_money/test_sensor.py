"""Test sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_metadata,
)
from homeassistant.const import PERCENTAGE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.recorder.common import async_wait_recording_done


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("currency", "expected_unit"),
    [
        ("USD", "USD"),
        ("CAD", "CAD"),
        ("EUR", "EUR"),
        ("GBP", "GBP"),
    ],
)
async def test_monetary_sensors_use_configured_currency(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    currency: str,
    expected_unit: str,
) -> None:
    """Test that monetary sensors use the configured HA currency."""
    await hass.config.async_update(currency=currency)

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Test account balance sensor (monetary)
    state = hass.states.get("sensor.rando_bank_checking_balance")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == expected_unit
    assert state.attributes["device_class"] == "monetary"

    # Test cashflow sensor (monetary)
    state = hass.states.get("sensor.cashflow_income_year_to_date")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == expected_unit
    assert state.attributes["device_class"] == "monetary"

    # Test value sensor (monetary)
    state = hass.states.get("sensor.vinaudit_2050_toyota_rav8_value")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == expected_unit
    assert state.attributes["device_class"] == "monetary"


async def test_non_monetary_sensors_not_affected_by_currency(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
) -> None:
    """Test that non-monetary sensors are not affected by currency setting."""
    await hass.config.async_update(currency="CAD")

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Test timestamp sensor (should have no unit)
    state = hass.states.get("sensor.rando_bank_checking_data_age")
    assert state is not None
    assert state.attributes["device_class"] == "timestamp"
    assert "unit_of_measurement" not in state.attributes

    # Test savings rate sensor (should use percentage, not currency)
    state = hass.states.get("sensor.cashflow_savings_rate")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    assert "device_class" not in state.attributes


@pytest.mark.usefixtures("recorder_mock")
async def test_statistics_migration_from_dollar_symbol(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
) -> None:
    """Test that statistics with '$' unit are migrated to configured currency."""
    await hass.config.async_update(currency="USD")

    # First, set up the integration to create entities
    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await async_wait_recording_done(hass)

    # Add external statistics with old "$" unit to simulate pre-migration data
    entity_id = "sensor.rando_bank_checking_balance"
    now = dt_util.utcnow()

    async_add_external_statistics(
        hass,
        {
            "has_mean": False,
            "has_sum": True,
            "mean_type": StatisticMeanType.NONE,
            "name": "Test Balance",
            "source": "recorder",
            "statistic_id": entity_id,
            "unit_class": None,
            "unit_of_measurement": "$",
        },
        [{"start": now, "sum": 1000.0, "state": 1000.0}],
    )
    await async_wait_recording_done(hass)

    # Verify initial statistics have "$" unit
    metadata = get_metadata(hass, statistic_ids={entity_id})
    assert entity_id in metadata
    assert metadata[entity_id][1]["unit_of_measurement"] == "$"

    # Unload and reload to trigger migration
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    # Verify statistics were migrated to configured currency
    metadata = get_metadata(hass, statistic_ids={entity_id})
    assert entity_id in metadata
    assert metadata[entity_id][1]["unit_of_measurement"] == "USD"
