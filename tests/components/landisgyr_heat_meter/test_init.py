"""Test the Landis + Gyr Heat Meter init."""

from homeassistant.components.landisgyr_heat_meter.const import (
    DOMAIN as LANDISGYR_HEAT_METER_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_unload_entry(hass):
    """Test removing config entry."""
    entry = MockConfigEntry(
        domain="landisgyr_heat_meter",
        title="LUGCUH50",
        data={CONF_DEVICE: "/dev/1234", "device_number": "123456"},
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "landisgyr_heat_meter" in hass.config.components

    assert await hass.config_entries.async_remove(entry.entry_id)


async def test_migrate_entry(hass):
    """Test successful migration of entry data from version 1 to 2."""

    # Create entry (which itself is not changed in version 2)
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "12345",
    }
    entry = MockConfigEntry(
        domain="landisgyr_heat_meter",
        title="LUGCUH50",
        entry_id="987654321",
        data=entry_data,
    )

    assert entry.data == entry_data
    assert entry.version == 1

    entry.add_to_hass(hass)

    # Create entity entry to migrate to new unique ID
    registry = er.async_get(hass)
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        LANDISGYR_HEAT_METER_DOMAIN,
        "landisgyr_heat_meter_987654321_measuring_range_m3ph",
        suggested_object_id="heat_meter_measuring_range",
        config_entry=entry,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "landisgyr_heat_meter" in hass.config.components

    # Check if entity unique id is migrated successfully
    assert entry.version == 2
    entity = registry.async_get("sensor.heat_meter_measuring_range")
    assert entity.unique_id == "12345_measuring_range_m3ph"
