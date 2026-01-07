"""Test energy data storage and migration."""

from homeassistant.components.energy.data import EnergyManager
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
    assert source["stat_rate"] == "sensor.energy_battery_battery_discharge_power"


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
