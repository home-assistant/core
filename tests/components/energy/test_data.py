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
                    "stat_energy_from": "sensor.grid_import",
                    "stat_energy_to": None,
                    "stat_cost": None,
                    "stat_compensation": None,
                    "entity_energy_price": None,
                    "number_energy_price": None,
                    "entity_energy_price_export": None,
                    "number_energy_price_export": None,
                    "power_config": {
                        "stat_rate_inverted": "sensor.grid_power",
                    },
                    "cost_adjustment_day": 0,
                }
            ],
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    assert grid_source["stat_rate"] == "sensor.grid_power_inverted"


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
    """Test that multiple grid sources are allowed (like batteries)."""
    # Multiple grid sources should now pass validation
    result = ENERGY_SOURCE_SCHEMA(
        [
            {
                "type": "grid",
                "stat_energy_from": "sensor.grid1_import",
                "stat_energy_to": "sensor.grid1_export",
                "cost_adjustment_day": 0,
            },
            {
                "type": "grid",
                "stat_energy_from": "sensor.grid2_import",
                "stat_energy_to": None,
                "cost_adjustment_day": 0,
            },
        ]
    )
    assert len(result) == 2
    assert result[0]["stat_energy_from"] == "sensor.grid1_import"
    assert result[1]["stat_energy_from"] == "sensor.grid2_import"


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
                    "stat_energy_from": "sensor.grid_import",
                    "stat_energy_to": None,
                    "stat_cost": None,
                    "stat_compensation": None,
                    "entity_energy_price": None,
                    "number_energy_price": None,
                    "entity_energy_price_export": None,
                    "number_energy_price_export": None,
                    "power_config": {
                        "stat_rate": "sensor.grid_power",
                    },
                    "cost_adjustment_day": 0,
                }
            ],
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    # stat_rate should be set directly from power_config.stat_rate
    assert grid_source["stat_rate"] == "sensor.grid_power"


async def test_grid_new_format_validates_correctly() -> None:
    """Test that new unified grid format validates correctly."""
    # Valid grid source with import and export
    result = ENERGY_SOURCE_SCHEMA(
        [
            {
                "type": "grid",
                "stat_energy_from": "sensor.energy_import",
                "stat_energy_to": "sensor.energy_export",
                "stat_cost": None,
                "stat_compensation": None,
                "entity_energy_price": None,
                "number_energy_price": 0.15,
                "entity_energy_price_export": None,
                "number_energy_price_export": 0.08,
                "cost_adjustment_day": 0,
            },
        ]
    )
    assert len(result) == 1
    assert result[0]["stat_energy_from"] == "sensor.energy_import"
    assert result[0]["stat_energy_to"] == "sensor.energy_export"

    # Valid grid source with import only (no export)
    result = ENERGY_SOURCE_SCHEMA(
        [
            {
                "type": "grid",
                "stat_energy_from": "sensor.energy_import",
                "stat_energy_to": None,
                "cost_adjustment_day": 0,
            },
        ]
    )
    assert result[0]["stat_energy_to"] is None


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
    """Test that grid without power_config is preserved unchanged."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    manager.data = manager.default_preferences()

    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "stat_energy_from": "sensor.grid_import",
                    "stat_energy_to": None,
                    "stat_cost": None,
                    "stat_compensation": None,
                    "entity_energy_price": None,
                    "number_energy_price": None,
                    "entity_energy_price_export": None,
                    "number_energy_price_export": None,
                    # No power_config, just stat_rate directly
                    "stat_rate": "sensor.grid_power",
                    "cost_adjustment_day": 0,
                }
            ],
        }
    )

    assert manager.data is not None
    grid_source = manager.data["energy_sources"][0]
    # stat_rate should be preserved unchanged
    assert grid_source["stat_rate"] == "sensor.grid_power"
    assert "power_config" not in grid_source


async def test_grid_migration_single_import_export(hass: HomeAssistant) -> None:
    """Test migration from legacy format with 1 import + 1 export creates 1 grid."""
    # Create legacy format data (v1.2) with flow_from/flow_to arrays
    old_data = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [
                    {
                        "stat_energy_from": "sensor.grid_import",
                        "stat_cost": "sensor.grid_cost",
                        "entity_energy_price": None,
                        "number_energy_price": None,
                    }
                ],
                "flow_to": [
                    {
                        "stat_energy_to": "sensor.grid_export",
                        "stat_compensation": None,
                        "entity_energy_price": "sensor.sell_price",
                        "number_energy_price": None,
                    }
                ],
                "cost_adjustment_day": 0.5,
            }
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }

    # Save with old version (1.2) - migration will run to upgrade to 1.3
    old_store = storage.Store(hass, 1, "energy", minor_version=2)
    await old_store.async_save(old_data)

    # Load with manager - should trigger migration
    manager = EnergyManager(hass)
    await manager.async_initialize()

    # Verify migration created unified grid source
    assert manager.data is not None
    assert len(manager.data["energy_sources"]) == 1

    grid = manager.data["energy_sources"][0]
    assert grid["type"] == "grid"
    assert grid["stat_energy_from"] == "sensor.grid_import"
    assert grid["stat_energy_to"] == "sensor.grid_export"
    assert grid["stat_cost"] == "sensor.grid_cost"
    assert grid["stat_compensation"] is None
    assert grid["entity_energy_price"] is None
    assert grid["entity_energy_price_export"] == "sensor.sell_price"
    assert grid["cost_adjustment_day"] == 0.5

    # Should not have legacy fields
    assert "flow_from" not in grid
    assert "flow_to" not in grid


async def test_grid_migration_multiple_imports_exports_paired(
    hass: HomeAssistant,
) -> None:
    """Test migration with 2 imports + 2 exports creates 2 paired grids."""
    old_data = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [
                    {
                        "stat_energy_from": "sensor.grid_import_1",
                        "stat_cost": None,
                        "entity_energy_price": None,
                        "number_energy_price": 0.15,
                    },
                    {
                        "stat_energy_from": "sensor.grid_import_2",
                        "stat_cost": None,
                        "entity_energy_price": None,
                        "number_energy_price": 0.20,
                    },
                ],
                "flow_to": [
                    {
                        "stat_energy_to": "sensor.grid_export_1",
                        "stat_compensation": None,
                        "entity_energy_price": None,
                        "number_energy_price": 0.08,
                    },
                    {
                        "stat_energy_to": "sensor.grid_export_2",
                        "stat_compensation": None,
                        "entity_energy_price": None,
                        "number_energy_price": 0.05,
                    },
                ],
                "cost_adjustment_day": 0,
            }
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }

    old_store = storage.Store(hass, 1, "energy", minor_version=2)
    await old_store.async_save(old_data)

    manager = EnergyManager(hass)
    await manager.async_initialize()

    assert manager.data is not None
    assert len(manager.data["energy_sources"]) == 2

    # First grid: paired import_1 with export_1
    grid1 = manager.data["energy_sources"][0]
    assert grid1["stat_energy_from"] == "sensor.grid_import_1"
    assert grid1["stat_energy_to"] == "sensor.grid_export_1"
    assert grid1["number_energy_price"] == 0.15
    assert grid1["number_energy_price_export"] == 0.08

    # Second grid: paired import_2 with export_2
    grid2 = manager.data["energy_sources"][1]
    assert grid2["stat_energy_from"] == "sensor.grid_import_2"
    assert grid2["stat_energy_to"] == "sensor.grid_export_2"
    assert grid2["number_energy_price"] == 0.20
    assert grid2["number_energy_price_export"] == 0.05


async def test_grid_migration_more_imports_than_exports(hass: HomeAssistant) -> None:
    """Test migration with 3 imports + 1 export creates 3 grids (first has export)."""
    old_data = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [
                    {"stat_energy_from": "sensor.import_1"},
                    {"stat_energy_from": "sensor.import_2"},
                    {"stat_energy_from": "sensor.import_3"},
                ],
                "flow_to": [
                    {"stat_energy_to": "sensor.export_1"},
                ],
                "cost_adjustment_day": 0,
            }
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }

    old_store = storage.Store(hass, 1, "energy", minor_version=2)
    await old_store.async_save(old_data)

    manager = EnergyManager(hass)
    await manager.async_initialize()

    assert manager.data is not None
    assert len(manager.data["energy_sources"]) == 3

    # First grid: has both import and export
    grid1 = manager.data["energy_sources"][0]
    assert grid1["stat_energy_from"] == "sensor.import_1"
    assert grid1["stat_energy_to"] == "sensor.export_1"

    # Second and third grids: import only
    grid2 = manager.data["energy_sources"][1]
    assert grid2["stat_energy_from"] == "sensor.import_2"
    assert grid2["stat_energy_to"] is None

    grid3 = manager.data["energy_sources"][2]
    assert grid3["stat_energy_from"] == "sensor.import_3"
    assert grid3["stat_energy_to"] is None


async def test_grid_migration_with_power(hass: HomeAssistant) -> None:
    """Test migration preserves power config and stat_rate from first grid.

    Note: Migration preserves the original stat_rate value from the legacy power array.
    The stat_rate regeneration from power_config only happens during async_update()
    for new data submissions, not during storage migration.
    """
    old_data = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [
                    {"stat_energy_from": "sensor.grid_import"},
                ],
                "flow_to": [
                    {"stat_energy_to": "sensor.grid_export"},
                ],
                "power": [
                    {
                        "stat_rate": "sensor.grid_power",
                        "power_config": {"stat_rate_inverted": "sensor.grid_power"},
                    }
                ],
                "cost_adjustment_day": 0,
            }
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }

    old_store = storage.Store(hass, 1, "energy", minor_version=2)
    await old_store.async_save(old_data)

    manager = EnergyManager(hass)
    await manager.async_initialize()

    assert manager.data is not None
    grid = manager.data["energy_sources"][0]

    # Verify power_config is preserved
    assert grid["power_config"] == {"stat_rate_inverted": "sensor.grid_power"}

    # Migration preserves the original stat_rate value from the legacy power array
    # (stat_rate regeneration from power_config only happens in async_update)
    assert grid["stat_rate"] == "sensor.grid_power"


async def test_grid_migration_import_only(hass: HomeAssistant) -> None:
    """Test migration with imports but no exports creates import-only grids."""
    old_data = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [
                    {"stat_energy_from": "sensor.grid_import"},
                ],
                "flow_to": [],
                "cost_adjustment_day": 0,
            }
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }

    old_store = storage.Store(hass, 1, "energy", minor_version=2)
    await old_store.async_save(old_data)

    manager = EnergyManager(hass)
    await manager.async_initialize()

    assert manager.data is not None
    assert len(manager.data["energy_sources"]) == 1

    grid = manager.data["energy_sources"][0]
    assert grid["stat_energy_from"] == "sensor.grid_import"
    assert grid["stat_energy_to"] is None


async def test_grid_migration_power_only(hass: HomeAssistant) -> None:
    """Test migration with only power configured (no import/export meters)."""
    old_data = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [],
                "flow_to": [],
                "power": [
                    {"stat_rate": "sensor.grid_power"},
                ],
                "cost_adjustment_day": 0.5,
            }
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }

    old_store = storage.Store(hass, 1, "energy", minor_version=2)
    await old_store.async_save(old_data)

    manager = EnergyManager(hass)
    await manager.async_initialize()

    assert manager.data is not None
    assert len(manager.data["energy_sources"]) == 1

    grid = manager.data["energy_sources"][0]
    assert grid["type"] == "grid"
    # No import or export meters
    assert grid["stat_energy_from"] is None
    assert grid["stat_energy_to"] is None
    # Power is preserved
    assert grid["stat_rate"] == "sensor.grid_power"
    assert grid["cost_adjustment_day"] == 0.5


async def test_grid_new_format_no_migration_needed(hass: HomeAssistant) -> None:
    """Test that new format data doesn't get migrated."""
    new_data = {
        "energy_sources": [
            {
                "type": "grid",
                "stat_energy_from": "sensor.grid_import",
                "stat_energy_to": "sensor.grid_export",
                "stat_cost": None,
                "stat_compensation": None,
                "entity_energy_price": None,
                "number_energy_price": 0.15,
                "entity_energy_price_export": None,
                "number_energy_price_export": 0.08,
                "cost_adjustment_day": 0,
            }
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }

    # Save with current version (1.3)
    old_store = storage.Store(hass, 1, "energy", minor_version=3)
    await old_store.async_save(new_data)

    manager = EnergyManager(hass)
    await manager.async_initialize()

    assert manager.data is not None
    assert len(manager.data["energy_sources"]) == 1
    grid = manager.data["energy_sources"][0]
    assert grid["stat_energy_from"] == "sensor.grid_import"
    assert grid["stat_energy_to"] == "sensor.grid_export"


async def test_grid_validation_single_import_price() -> None:
    """Test that grid validation rejects both entity and number import price."""
    with pytest.raises(
        vol.Invalid, match="Define either an entity or a fixed number for import price"
    ):
        ENERGY_SOURCE_SCHEMA(
            [
                {
                    "type": "grid",
                    "stat_energy_from": "sensor.grid_import",
                    "entity_energy_price": "sensor.price",
                    "number_energy_price": 0.15,
                    "cost_adjustment_day": 0,
                }
            ]
        )


async def test_grid_validation_single_export_price() -> None:
    """Test that grid validation rejects both entity and number export price."""
    with pytest.raises(
        vol.Invalid, match="Define either an entity or a fixed number for export price"
    ):
        ENERGY_SOURCE_SCHEMA(
            [
                {
                    "type": "grid",
                    "stat_energy_from": "sensor.grid_import",
                    "stat_energy_to": "sensor.grid_export",
                    "entity_energy_price_export": "sensor.sell_price",
                    "number_energy_price_export": 0.08,
                    "cost_adjustment_day": 0,
                }
            ]
        )
