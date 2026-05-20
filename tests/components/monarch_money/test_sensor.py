"""Test sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.monarch_money import async_migrate_entry
from homeassistant.components.monarch_money.config_flow import MonarchMoneyConfigFlow
from homeassistant.components.monarch_money.const import DEFAULT_CURRENCY, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
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
    "currency",
    [
        "USD",
        "CAD",
        "EUR",
        "GBP",
    ],
)
async def test_monetary_sensors_ignore_hass_currency(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    currency: str,
) -> None:
    """Test that monetary sensors ignore the configured HA currency."""
    await hass.config.async_update(currency=currency)

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.rando_bank_checking_balance")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == DEFAULT_CURRENCY
    assert state.attributes["device_class"] == "monetary"

    state = hass.states.get("sensor.cashflow_income_year_to_date")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == DEFAULT_CURRENCY
    assert state.attributes["device_class"] == "monetary"

    state = hass.states.get("sensor.vinaudit_2050_toyota_rav8_value")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == DEFAULT_CURRENCY
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

    state = hass.states.get("sensor.rando_bank_checking_data_age")
    assert state is not None
    assert state.attributes["device_class"] == "timestamp"
    assert "unit_of_measurement" not in state.attributes

    state = hass.states.get("sensor.cashflow_savings_rate")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    assert "device_class" not in state.attributes


@pytest.mark.usefixtures("recorder_mock")
async def test_statistics_migration_called_for_monetary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test statistics migration updates existing monetary sensors."""
    await hass.config.async_update(currency="USD")

    mock_config_entry.add_to_hass(hass)
    _add_migration_entity_registry_entries(entity_registry, mock_config_entry)

    with patch(
        "homeassistant.components.monarch_money.async_update_statistics_metadata"
    ) as mock_update_stats:
        assert await async_migrate_entry(hass, mock_config_entry)

    called_entity_ids = {call.args[1] for call in mock_update_stats.call_args_list}
    assert called_entity_ids == {
        "sensor.cashflow_income_year_to_date",
        "sensor.rando_bank_checking_balance",
    }
    for call in mock_update_stats.call_args_list:
        assert call.kwargs["new_unit_of_measurement"] == DEFAULT_CURRENCY

    assert mock_config_entry.minor_version == MonarchMoneyConfigFlow.MINOR_VERSION


async def test_statistics_migration_skips_metadata_without_recorder(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test statistics migration skips metadata updates without recorder."""
    mock_config_entry.add_to_hass(hass)
    _add_migration_entity_registry_entries(entity_registry, mock_config_entry)

    with patch(
        "homeassistant.components.monarch_money.async_update_statistics_metadata",
        side_effect=AssertionError("Statistics metadata should not be updated"),
    ):
        assert await async_migrate_entry(hass, mock_config_entry)

    assert mock_config_entry.minor_version == MonarchMoneyConfigFlow.MINOR_VERSION


def _add_migration_entity_registry_entries(
    entity_registry: er.EntityRegistry, mock_config_entry: MockConfigEntry
) -> None:
    """Add entity registry entries for statistics migration tests."""
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "222260252323873333_checking_currentBalance",
        config_entry=mock_config_entry,
        original_device_class=SensorDeviceClass.MONETARY,
        suggested_object_id="rando_bank_checking_balance",
    )
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "222260252323873333_sum_income",
        config_entry=mock_config_entry,
        original_device_class=SensorDeviceClass.MONETARY,
        suggested_object_id="cashflow_income_year_to_date",
    )
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "222260252323873333_checking_age",
        config_entry=mock_config_entry,
        original_device_class=SensorDeviceClass.TIMESTAMP,
        suggested_object_id="rando_bank_checking_data_age",
    )
