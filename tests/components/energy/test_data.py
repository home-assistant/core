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
