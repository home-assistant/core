"""Test sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import PERCENTAGE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


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


async def test_statistics_migration_called_for_monetary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test that statistics migration is called for existing monetary sensors on setup."""
    await hass.config.async_update(currency="USD")

    # Add entry to hass first so we can add entities to it
    mock_config_entry.add_to_hass(hass)

    # Pre-populate entity registry with existing monetary sensor entries
    # This simulates a previous installation that had these entities
    entity_registry.async_get_or_create(
        "sensor",
        "monarch_money",
        "222260252323873333_checking_currentBalance",
        config_entry=mock_config_entry,
        original_device_class="monetary",
        suggested_object_id="rando_bank_checking_balance",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "monarch_money",
        "222260252323873333_sum_income",
        config_entry=mock_config_entry,
        original_device_class="monetary",
        suggested_object_id="cashflow_income_year_to_date",
    )
    # Add a non-monetary sensor to verify it's not migrated
    entity_registry.async_get_or_create(
        "sensor",
        "monarch_money",
        "222260252323873333_checking_age",
        config_entry=mock_config_entry,
        original_device_class="timestamp",
        suggested_object_id="rando_bank_checking_data_age",
    )

    with (
        patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]),
        patch(
            "homeassistant.components.monarch_money.async_update_statistics_metadata"
        ) as mock_update_stats,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify async_update_statistics_metadata was called for monetary sensors
    assert mock_update_stats.call_count == 2  # Only the 2 monetary sensors

    # Collect all entity_ids that were called
    called_entity_ids = {call.args[1] for call in mock_update_stats.call_args_list}

    # Verify monetary sensors were included
    assert "sensor.rando_bank_checking_balance" in called_entity_ids
    assert "sensor.cashflow_income_year_to_date" in called_entity_ids

    # Verify non-monetary sensor was NOT included
    assert "sensor.rando_bank_checking_data_age" not in called_entity_ids

    # Verify all calls used the configured currency
    for call in mock_update_stats.call_args_list:
        assert call.kwargs["new_unit_of_measurement"] == "USD"
