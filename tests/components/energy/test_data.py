"""Test energy data storage and migration."""

import pytest
import voluptuous as vol

from homeassistant.components.energy.data import (
    EnergyManager,
    _flow_from_ensure_single_price,
    _generate_unique_value_validator,
    _validate_power_config,
    check_type_limits,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage


async def test_energy_preferences_no_migration_needed(hass: HomeAssistant) -> None:
    """Test that new data format doesn't get migrated."""
    # Create new format data (already has device_consumption_water field)
    new_data = {
        "energy_sources": [],
        "device_consumption": [],
        "device_consumption_water": [
            {"stat_consumption": "sensor.water_meter", "name": "Water heater"}
        ],
    }

    # Save data that already has the new field
    old_store = storage.Store(hass, 1, "energy", minor_version=1)
    await old_store.async_save(new_data)

    # Load it with manager
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Verify the data is unchanged
    assert manager.data is not None
    assert manager.data["device_consumption_water"] == [
        {"stat_consumption": "sensor.water_meter", "name": "Water heater"}
    ]


async def test_energy_preferences_default(hass: HomeAssistant) -> None:
    """Test default preferences include device_consumption_water."""
    defaults = EnergyManager.default_preferences()

    assert "energy_sources" in defaults
    assert "device_consumption" in defaults
    assert "device_consumption_water" in defaults
    assert defaults["device_consumption_water"] == []


async def test_energy_preferences_empty_store(hass: HomeAssistant) -> None:
    """Test loading with no existing data."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Verify data is None when no existing data
    assert manager.data is None


async def test_energy_preferences_migration_from_old_version(
    hass: HomeAssistant,
) -> None:
    """Test that device_consumption_water is added when migrating from v1.1 to v1.2."""
    # Create version 1.1 data without device_consumption_water (old version)
    old_data = {
        "energy_sources": [],
        "device_consumption": [],
    }

    # Save with old version (1.1) - migration will run to upgrade to 1.2
    old_store = storage.Store(hass, 1, "energy", minor_version=1)
    await old_store.async_save(old_data)

    # Load with manager - should trigger migration
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Verify the field was added by migration
    assert manager.data is not None
    assert "device_consumption_water" in manager.data
    assert manager.data["device_consumption_water"] == []


async def test_flow_from_ensure_single_price_both_set() -> None:
    """Test that validation fails when both price sources are set."""
    val = {
        "stat_energy_from": "sensor.energy",
        "entity_energy_price": "sensor.price",
        "number_energy_price": 1.0,
    }
    with pytest.raises(vol.Invalid, match="Define either an entity or a fixed number"):
        _flow_from_ensure_single_price(val)


async def test_flow_from_ensure_single_price_valid() -> None:
    """Test validation passes with only one price source."""
    val = {
        "stat_energy_from": "sensor.energy",
        "entity_energy_price": "sensor.price",
        "number_energy_price": None,
    }
    result = _flow_from_ensure_single_price(val)
    assert result == val


async def test_generate_unique_value_validator_duplicates() -> None:
    """Test that duplicate values are rejected."""
    validator = _generate_unique_value_validator("stat_energy_from")
    values = [
        {"stat_energy_from": "sensor.energy1"},
        {"stat_energy_from": "sensor.energy1"},  # duplicate
    ]
    with pytest.raises(
        vol.Invalid, match="Cannot specify sensor.energy1 more than once"
    ):
        validator(values)


async def test_generate_unique_value_validator_valid() -> None:
    """Test that unique values pass validation."""
    validator = _generate_unique_value_validator("stat_energy_from")
    values = [
        {"stat_energy_from": "sensor.energy1"},
        {"stat_energy_from": "sensor.energy2"},
    ]
    result = validator(values)
    assert result == values


async def test_check_type_limits_multiple_grid() -> None:
    """Test that multiple grid sources are rejected."""
    sources = [
        {"type": "grid", "flow_from": [], "flow_to": [], "cost_adjustment_day": 0},
        {"type": "grid", "flow_from": [], "flow_to": [], "cost_adjustment_day": 0},
    ]
    with pytest.raises(vol.Invalid, match="You cannot have more than 1 grid source"):
        check_type_limits(sources)


async def test_check_type_limits_valid() -> None:
    """Test that valid source combinations pass."""
    sources = [
        {"type": "grid", "flow_from": [], "flow_to": [], "cost_adjustment_day": 0},
        {"type": "solar", "stat_energy_from": "sensor.solar"},
    ]
    result = check_type_limits(sources)
    assert result == sources


async def test_async_update_from_none(hass: HomeAssistant) -> None:
    """Test updating preferences when data is None."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Data should be None initially
    assert manager.data is None

    # Update with new preferences
    await manager.async_update({"energy_sources": []})

    # Data should now be set with defaults plus our update
    assert manager.data is not None
    assert manager.data["energy_sources"] == []
    assert manager.data["device_consumption"] == []
    assert manager.data["device_consumption_water"] == []


async def test_async_update_with_listeners(hass: HomeAssistant) -> None:
    """Test that update listeners are called when data is updated."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    listener_called = []

    async def listener() -> None:
        listener_called.append(True)

    manager.async_listen_updates(listener)

    # Update preferences - listener should be called
    await manager.async_update({"energy_sources": []})

    assert len(listener_called) == 1


async def test_async_update_without_listeners(hass: HomeAssistant) -> None:
    """Test that update works without listeners."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # No listeners registered, update should still work
    await manager.async_update({"energy_sources": []})

    assert manager.data is not None
    assert manager.data["energy_sources"] == []


async def test_async_update_existing_data(hass: HomeAssistant) -> None:
    """Test updating preferences when data already exists."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # First update to set data
    await manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.a"}]}
    )
    assert manager.data is not None
    assert manager.data["device_consumption"] == [{"stat_consumption": "sensor.a"}]

    # Second update should copy existing data and merge
    await manager.async_update(
        {"energy_sources": [{"type": "solar", "stat_energy_from": "sensor.solar"}]}
    )
    assert manager.data["device_consumption"] == [{"stat_consumption": "sensor.a"}]
    assert manager.data["energy_sources"] == [
        {"type": "solar", "stat_energy_from": "sensor.solar"}
    ]


async def test_validate_power_config_empty() -> None:
    """Test that empty power_config is rejected."""
    with pytest.raises(vol.Invalid, match="power_config must have at least one option"):
        _validate_power_config({})


async def test_validate_power_config_multiple_methods() -> None:
    """Test that multiple power config methods are rejected."""
    val = {
        "stat_rate": "sensor.power",
        "stat_rate_inverted": "sensor.power_inv",
    }
    with pytest.raises(
        vol.Invalid,
        match="power_config must use only one configuration method",
    ):
        _validate_power_config(val)


async def test_validate_power_config_valid_stat_rate() -> None:
    """Test valid power_config with stat_rate."""
    val = {"stat_rate": "sensor.power"}
    result = _validate_power_config(val)
    assert result == val


async def test_validate_power_config_valid_inverted() -> None:
    """Test valid power_config with stat_rate_inverted."""
    val = {"stat_rate_inverted": "sensor.power_inv"}
    result = _validate_power_config(val)
    assert result == val


async def test_validate_power_config_valid_combined() -> None:
    """Test valid power_config with stat_rate_from/to."""
    val = {"stat_rate_from": "sensor.power_from", "stat_rate_to": "sensor.power_to"}
    result = _validate_power_config(val)
    assert result == val


async def test_process_battery_power_with_stat_rate(hass: HomeAssistant) -> None:
    """Test battery power processing with direct stat_rate config."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Update with battery source having power_config with stat_rate
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_discharge",
                    "stat_energy_to": "sensor.battery_charge",
                    "power_config": {"stat_rate": "sensor.battery_power"},
                }
            ]
        }
    )

    assert manager.data is not None
    battery_source = manager.data["energy_sources"][0]
    # stat_rate should be set from power_config
    assert battery_source["stat_rate"] == "sensor.battery_power"


async def test_process_battery_power_with_inverted(hass: HomeAssistant) -> None:
    """Test battery power processing with inverted config generates entity_id."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Update with battery source having power_config with stat_rate_inverted
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_discharge",
                    "stat_energy_to": "sensor.battery_charge",
                    "power_config": {"stat_rate_inverted": "sensor.battery_power_inv"},
                }
            ]
        }
    )

    assert manager.data is not None
    battery_source = manager.data["energy_sources"][0]
    # stat_rate should be set to generated entity_id (source + _inverted suffix)
    assert "stat_rate" in battery_source
    assert battery_source["stat_rate"] == "sensor.battery_power_inv_inverted"


async def test_process_battery_power_without_power_config(hass: HomeAssistant) -> None:
    """Test battery source without power_config is unchanged."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Update with battery source without power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_discharge",
                    "stat_energy_to": "sensor.battery_charge",
                }
            ]
        }
    )

    assert manager.data is not None
    battery_source = manager.data["energy_sources"][0]
    # stat_rate should not be set
    assert "stat_rate" not in battery_source


async def test_process_grid_power_with_stat_rate(hass: HomeAssistant) -> None:
    """Test grid power processing with direct stat_rate config."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Update with grid source having power config with stat_rate
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "cost_adjustment_day": 0,
                    "power": [{"power_config": {"stat_rate": "sensor.grid_power"}}],
                }
            ]
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    assert "power" in grid_source
    # stat_rate should be set from power_config
    assert grid_source["power"][0]["stat_rate"] == "sensor.grid_power"


async def test_process_grid_power_with_inverted(hass: HomeAssistant) -> None:
    """Test grid power processing with inverted config generates entity_id."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Update with grid source having power config with stat_rate_inverted
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "cost_adjustment_day": 0,
                    "power": [
                        {
                            "power_config": {
                                "stat_rate_inverted": "sensor.grid_power_inv"
                            }
                        }
                    ],
                }
            ]
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    assert "power" in grid_source
    # stat_rate should be set to generated entity_id (source + _inverted suffix)
    assert grid_source["power"][0]["stat_rate"] == "sensor.grid_power_inv_inverted"


async def test_process_grid_power_without_power_config(hass: HomeAssistant) -> None:
    """Test grid power source without power_config is unchanged."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Update with grid source having power but no power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "cost_adjustment_day": 0,
                    "power": [{"stat_rate": "sensor.existing_power"}],
                }
            ]
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    assert "power" in grid_source
    # stat_rate should remain as provided
    assert grid_source["power"][0]["stat_rate"] == "sensor.existing_power"


async def test_process_grid_without_power(hass: HomeAssistant) -> None:
    """Test grid source without power is unchanged."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Update with grid source without power
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "cost_adjustment_day": 0,
                }
            ]
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    # power should not be added
    assert "power" not in grid_source
