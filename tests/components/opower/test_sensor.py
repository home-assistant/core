"""Tests for the Opower sensor platform."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from opower import CostRead
import pytest

from homeassistant.components.opower.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_sensors(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test the creation and values of Opower sensors."""
    mock_opower_api.async_get_cost_reads.return_value = [
        CostRead(
            start_time=dt_util.as_utc(datetime(2023, 1, 1, 8)),
            end_time=dt_util.as_utc(datetime(2023, 1, 1, 9)),
            consumption=1.5,
            provided_cost=0.5,
        ),
    ]

    with patch(
        "homeassistant.components.opower.coordinator.dt_util.utcnow"
    ) as mock_utcnow:
        mock_utcnow.return_value = datetime(2023, 1, 2, 8, 0, 0, tzinfo=dt_util.UTC)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # Check electric sensors
    entry = entity_registry.async_get(
        "sensor.elec_account_111111_current_bill_electric_usage_to_date"
    )
    assert entry
    assert entry.unique_id == "pge_111111_elec_usage_to_date"
    state = hass.states.get(
        "sensor.elec_account_111111_current_bill_electric_usage_to_date"
    )
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.state == "100"

    entry = entity_registry.async_get(
        "sensor.elec_account_111111_current_bill_electric_cost_to_date"
    )
    assert entry
    assert entry.unique_id == "pge_111111_elec_cost_to_date"
    state = hass.states.get(
        "sensor.elec_account_111111_current_bill_electric_cost_to_date"
    )
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "USD"
    assert state.state == "20.0"

    entry = entity_registry.async_get("sensor.elec_account_111111_last_changed")
    assert entry
    assert entry.unique_id == "pge_111111_last_changed"
    state = hass.states.get("sensor.elec_account_111111_last_changed")
    assert state
    assert state.state == "2023-01-01T16:00:00+00:00"

    entry = entity_registry.async_get("sensor.elec_account_111111_last_updated")
    assert entry
    assert entry.unique_id == "pge_111111_last_updated"
    state = hass.states.get("sensor.elec_account_111111_last_updated")
    assert state
    assert state.state == "2023-01-02T08:00:00+00:00"

    # Check gas sensors
    entry = entity_registry.async_get(
        "sensor.gas_account_222222_current_bill_gas_usage_to_date"
    )
    assert entry
    assert entry.unique_id == "pge_222222_gas_usage_to_date"
    state = hass.states.get("sensor.gas_account_222222_current_bill_gas_usage_to_date")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfVolume.CUBIC_METERS
    # Convert 50 CCF to m³
    assert float(state.state) == pytest.approx(50 * 2.83168, abs=1e-3)

    entry = entity_registry.async_get(
        "sensor.gas_account_222222_current_bill_gas_cost_to_date"
    )
    assert entry
    assert entry.unique_id == "pge_222222_gas_cost_to_date"
    state = hass.states.get("sensor.gas_account_222222_current_bill_gas_cost_to_date")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "USD"
    assert state.state == "15.0"

    entry = entity_registry.async_get("sensor.gas_account_222222_last_changed")
    assert entry
    assert entry.unique_id == "pge_222222_last_changed"
    state = hass.states.get("sensor.gas_account_222222_last_changed")
    assert state
    assert state.state == "2023-01-01T16:00:00+00:00"

    entry = entity_registry.async_get("sensor.gas_account_222222_last_updated")
    assert entry
    assert entry.unique_id == "pge_222222_last_updated"
    state = hass.states.get("sensor.gas_account_222222_last_updated")
    assert state
    assert state.state == "2023-01-02T08:00:00+00:00"


async def test_dynamic_and_stale_devices(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the dynamic addition and removal of Opower devices."""
    original_accounts = mock_opower_api.async_get_accounts.return_value
    original_forecasts = mock_opower_api.async_get_forecast.return_value

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    initial_device_ids = {device.id for device in devices}
    initial_entity_ids = {entity.entity_id for entity in entities}
    # Ensure we actually created some devices and entities for this entry
    assert initial_device_ids
    assert initial_entity_ids

    # Remove the second account and update data
    mock_opower_api.async_get_accounts.return_value = [original_accounts[0]]
    mock_opower_api.async_get_forecast.return_value = [original_forecasts[0]]

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    device_ids_after_removal = {device.id for device in devices}
    entity_ids_after_removal = {entity.entity_id for entity in entities}
    # After removing one account, we should have removed some devices/entities
    # but not added any new ones.
    assert device_ids_after_removal <= initial_device_ids
    assert entity_ids_after_removal <= initial_entity_ids
    assert device_ids_after_removal != initial_device_ids
    assert entity_ids_after_removal != initial_entity_ids

    # Add back the second account
    mock_opower_api.async_get_accounts.return_value = original_accounts
    mock_opower_api.async_get_forecast.return_value = original_forecasts

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    device_ids_after_restore = {device.id for device in devices}
    entity_ids_after_restore = {entity.entity_id for entity in entities}
    # After restoring the second account, we should be back to the original
    # number of devices and entities (IDs themselves may change on re-create).
    assert len(device_ids_after_restore) == len(initial_device_ids)
    assert len(entity_ids_after_restore) == len(initial_entity_ids)


async def test_stale_device_removed_on_load(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a stale device present before setup is removed on first load."""
    # Simulate a device that was created by a previous version / old account
    # and is already registered before the integration sets up.
    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "pge_stale_account_99999")},
    )
    assert device_registry.async_get(stale_device.id) is not None

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Stale device should have been removed on first coordinator update
    assert device_registry.async_get(stale_device.id) is None

    # Active devices for known accounts should still be present,
    # and the stale identifier should no longer be registered.
    active_devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    active_identifiers = {
        identifier
        for device in active_devices
        for (_domain, identifier) in device.identifiers
    }
    assert "pge_111111" in active_identifiers
    assert "pge_222222" in active_identifiers
    assert "pge_stale_account_99999" not in active_identifiers
