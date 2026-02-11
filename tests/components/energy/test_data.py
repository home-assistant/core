"""Test energy data storage and migration."""

import pytest
import voluptuous as vol

from homeassistant.components.energy.data import (
    ENERGY_SOURCE_SCHEMA,
    FLOW_FROM_GRID_SOURCE_SCHEMA,
    POWER_CONFIG_SCHEMA,
    EnergyManager,
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


async def test_battery_power_config_inverted_sets_stat_rate(
    hass: HomeAssistant,
) -> None:
    """Test that battery with inverted power_config sets stat_rate to generated entity_id."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    manager.data = manager.default_preferences()

    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )

    # Verify stat_rate was set to the expected entity_id
    assert manager.data is not None
    assert len(manager.data["energy_sources"]) == 1
    source = manager.data["energy_sources"][0]
    assert source["stat_rate"] == "sensor.battery_power_inverted"
    # Verify power_config is preserved
    assert source["power_config"] == {"stat_rate_inverted": "sensor.battery_power"}


async def test_battery_power_config_two_sensors_sets_stat_rate(
    hass: HomeAssistant,
) -> None:
    """Test that battery with two-sensor power_config sets stat_rate."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    manager.data = manager.default_preferences()

    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_from": "sensor.battery_discharge",
                        "stat_rate_to": "sensor.battery_charge",
                    },
                }
            ],
        }
    )

    assert manager.data is not None
    source = manager.data["energy_sources"][0]
    # Entity ID includes discharge sensor name to avoid collisions
    assert (
        source["stat_rate"]
        == "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )


async def test_grid_power_config_inverted_sets_stat_rate(
    hass: HomeAssistant,
) -> None:
    """Test that grid with inverted power_config sets stat_rate."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    manager.data = manager.default_preferences()

    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "power": [
                        {
                            "power_config": {
                                "stat_rate_inverted": "sensor.grid_power",
                            },
                        }
                    ],
                    "cost_adjustment_day": 0,
                }
            ],
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    assert grid_source["power"][0]["stat_rate"] == "sensor.grid_power_inverted"


async def test_power_config_standard_uses_stat_rate_directly(
    hass: HomeAssistant,
) -> None:
    """Test that power_config with standard stat_rate uses it directly."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    manager.data = manager.default_preferences()

    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate": "sensor.battery_power",
                    },
                }
            ],
        }
    )

    assert manager.data is not None
    source = manager.data["energy_sources"][0]
    # stat_rate should be set directly from power_config.stat_rate
    assert source["stat_rate"] == "sensor.battery_power"


async def test_battery_without_power_config_unchanged(hass: HomeAssistant) -> None:
    """Test that battery without power_config is unchanged."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    manager.data = manager.default_preferences()

    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "stat_rate": "sensor.battery_power",
                }
            ],
        }
    )

    assert manager.data is not None
    source = manager.data["energy_sources"][0]
    assert source["stat_rate"] == "sensor.battery_power"
    assert "power_config" not in source


async def test_power_config_takes_precedence_over_stat_rate(
    hass: HomeAssistant,
) -> None:
    """Test that power_config takes precedence when both are provided."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    manager.data = manager.default_preferences()

    # Frontend sends both stat_rate and power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "stat_rate": "sensor.battery_power",  # This should be ignored
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )

    assert manager.data is not None
    source = manager.data["energy_sources"][0]
    # stat_rate should be overwritten to point to the generated inverted sensor
    assert source["stat_rate"] == "sensor.battery_power_inverted"


async def test_power_config_validation_empty() -> None:
    """Test that empty power_config raises validation error."""
    with pytest.raises(vol.Invalid, match="power_config must have at least one option"):
        POWER_CONFIG_SCHEMA({})


async def test_power_config_validation_multiple_methods() -> None:
    """Test that power_config with multiple methods raises validation error."""
    # Both stat_rate and stat_rate_inverted (should fail due to Exclusive)
    with pytest.raises(vol.Invalid):
        POWER_CONFIG_SCHEMA(
            {
                "stat_rate": "sensor.power",
                "stat_rate_inverted": "sensor.power",
            }
        )

    # Both stat_rate and stat_rate_from/to (should fail due to Exclusive)
    with pytest.raises(vol.Invalid):
        POWER_CONFIG_SCHEMA(
            {
                "stat_rate": "sensor.power",
                "stat_rate_from": "sensor.discharge",
                "stat_rate_to": "sensor.charge",
            }
        )

    # Both stat_rate_inverted and stat_rate_from/to (should fail due to Exclusive)
    with pytest.raises(vol.Invalid):
        POWER_CONFIG_SCHEMA(
            {
                "stat_rate_inverted": "sensor.power",
                "stat_rate_from": "sensor.discharge",
                "stat_rate_to": "sensor.charge",
            }
        )


async def test_flow_from_validation_multiple_prices() -> None:
    """Test that flow_from validation rejects both entity and number price."""
    # Both entity_energy_price and number_energy_price should fail
    with pytest.raises(
        vol.Invalid, match="Define either an entity or a fixed number for the price"
    ):
        FLOW_FROM_GRID_SOURCE_SCHEMA(
            {
                "stat_energy_from": "sensor.energy",
                "entity_energy_price": "sensor.price",
                "number_energy_price": 0.15,
            }
        )


async def test_energy_sources_validation_multiple_grids() -> None:
    """Test that multiple grid sources are rejected."""
    # Multiple grid sources should fail validation
    with pytest.raises(vol.Invalid, match="You cannot have more than 1 grid source"):
        ENERGY_SOURCE_SCHEMA(
            [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "cost_adjustment_day": 0,
                },
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "cost_adjustment_day": 0,
                },
            ]
        )


async def test_power_config_validation_passes() -> None:
    """Test that valid power_config passes validation."""
    # Test standard stat_rate
    result = POWER_CONFIG_SCHEMA({"stat_rate": "sensor.power"})
    assert result == {"stat_rate": "sensor.power"}

    # Test inverted
    result = POWER_CONFIG_SCHEMA({"stat_rate_inverted": "sensor.power"})
    assert result == {"stat_rate_inverted": "sensor.power"}

    # Test two-sensor combined
    result = POWER_CONFIG_SCHEMA(
        {"stat_rate_from": "sensor.discharge", "stat_rate_to": "sensor.charge"}
    )
    assert result == {
        "stat_rate_from": "sensor.discharge",
        "stat_rate_to": "sensor.charge",
    }


async def test_grid_power_config_standard_stat_rate(hass: HomeAssistant) -> None:
    """Test that grid with power_config using standard stat_rate works correctly."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    manager.data = manager.default_preferences()

    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "power": [
                        {
                            "power_config": {
                                "stat_rate": "sensor.grid_power",
                            },
                        }
                    ],
                    "cost_adjustment_day": 0,
                }
            ],
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    # stat_rate should be set directly from power_config.stat_rate
    assert grid_source["power"][0]["stat_rate"] == "sensor.grid_power"


async def test_flow_from_duplicate_stat_energy_from() -> None:
    """Test that duplicate stat_energy_from values are rejected."""
    with pytest.raises(
        vol.Invalid, match="Cannot specify sensor.energy more than once"
    ):
        ENERGY_SOURCE_SCHEMA(
            [
                {
                    "type": "grid",
                    "flow_from": [
                        {
                            "stat_energy_from": "sensor.energy",
                            "stat_cost": None,
                            "entity_energy_price": None,
                            "number_energy_price": 0.15,
                        },
                        {
                            "stat_energy_from": "sensor.energy",  # Duplicate
                            "stat_cost": None,
                            "entity_energy_price": None,
                            "number_energy_price": 0.20,
                        },
                    ],
                    "flow_to": [],
                    "cost_adjustment_day": 0,
                },
            ]
        )


async def test_async_update_when_data_is_none(hass: HomeAssistant) -> None:
    """Test async_update when manager.data is None uses default preferences."""
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Ensure data is None (empty store)
    assert manager.data is None

    # Call async_update - should use default_preferences as base
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "solar",
                    "stat_energy_from": "sensor.solar_energy",
                    "config_entry_solar_forecast": None,
                }
            ],
        }
    )

    # Verify data was created with the update and default fields
    assert manager.data is not None
    assert len(manager.data["energy_sources"]) == 1
    assert manager.data["energy_sources"][0]["type"] == "solar"
    # Default fields should be present
    assert manager.data["device_consumption"] == []
    assert manager.data["device_consumption_water"] == []


async def test_grid_power_without_power_config(hass: HomeAssistant) -> None:
    """Test that grid power entry without power_config is preserved unchanged."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    manager.data = manager.default_preferences()

    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "power": [
                        {
                            # No power_config, just stat_rate directly
                            "stat_rate": "sensor.grid_power",
                        }
                    ],
                    "cost_adjustment_day": 0,
                }
            ],
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    # Power entry should be preserved unchanged
    assert len(grid_source["power"]) == 1
    assert grid_source["power"][0]["stat_rate"] == "sensor.grid_power"
    assert "power_config" not in grid_source["power"][0]
